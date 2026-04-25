"""
SCALE-Inspired Emergy Calculator — API REST com FastAPI.

Endpoints principais:
  GET  /                    → Interface web principal
  GET  /api/processes       → Lista todos os processos LCI
  POST /api/processes       → Adiciona novo processo
  DELETE /api/processes/{id}→ Remove processo
  POST /api/simulate        → Executa simulação de emergia
  GET  /api/export          → Exporta base LCI em JSON
  POST /api/import          → Importa base LCI de JSON
"""
import os
import json
import math
import tempfile
from typing import List, Optional
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from modules.lci_manager import (
    LCIRepository, LCIProcessFactory, LCIInput
)
from modules.emergy_calculator import EmergySimulator
from modules.observer import CalculationObserver

# ── App setup ─────────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = FastAPI(
    title="SCALE-Inspired Emergy Calculator",
    description=(
        "Sistema de cálculo de emergia baseado no software SCALE "
        "(Marvuglia et al., 2013). Implementa o algoritmo DFS com "
        "álgebra emergética de Odum (1996)."
    ),
    version="1.0.0",
)

app.mount(
    "/static",
    StaticFiles(directory=os.path.join(BASE_DIR, "static")),
    name="static"
)
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# ── Singletons ────────────────────────────────────────────────────────────────

repository = LCIRepository()
simulator = EmergySimulator(repository, strategy_name="dfs")
calc_observer = CalculationObserver()
simulator.attach(calc_observer)

# Carrega dados de exemplo na inicialização
_sample_path = os.path.join(BASE_DIR, "data", "sample_lci.json")
if os.path.exists(_sample_path):
    repository.load_from_file(_sample_path)


# ── Schemas Pydantic ──────────────────────────────────────────────────────────

class InputSchema(BaseModel):
    process_id: str
    amount: float = Field(gt=0, description="Quantidade consumida por unidade de saída")


class ProcessSchema(BaseModel):
    id: str = Field(description="Identificador único do processo")
    name: str
    type: str = Field(pattern="^(source|process)$")
    unit: str
    uev: float = Field(ge=0, description="Unit Emergy Value em sej/unidade")
    description: str = ""
    inputs: List[InputSchema] = []
    output_amount: float = Field(default=1.0, gt=0)


class SimulationRequest(BaseModel):
    target_process_id: str
    minflow: float = Field(default=1e-6, gt=0, le=1.0)
    strategy: str = Field(default="dfs", pattern="^(dfs|simplified)$")


def _safe(v: float) -> Optional[float]:
    """Converte inf/nan para None para serialização JSON segura."""
    if v is None or (isinstance(v, float) and (math.isinf(v) or math.isnan(v))):
        return None
    return v


class SimulationResponse(BaseModel):
    target_process_id: str
    target_name: str
    total_emergy_sej: float
    minflow_threshold: float
    strategy: str
    emergy_yield_ratio: Optional[float]
    environmental_load_ratio: Optional[float]
    sustainability_index: Optional[float]
    renewable_fraction: float
    contributions: List[dict]
    formatted_result: str


# ── HTML Routes ───────────────────────────────────────────────────────────────

@app.get("/", include_in_schema=False)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ── API: Processos LCI ────────────────────────────────────────────────────────

@app.get("/api/processes", response_model=List[ProcessSchema], tags=["LCI"])
async def list_processes():
    """Retorna todos os processos cadastrados na base LCI."""
    result = []
    for p in repository.get_all_processes():
        result.append(ProcessSchema(
            id=p.id, name=p.name, type=p.process_type,
            unit=p.unit, uev=p.uev, description=p.description,
            inputs=[InputSchema(process_id=i.process_id, amount=i.amount)
                    for i in p.inputs],
            output_amount=p.output_amount
        ))
    return result


@app.get("/api/processes/{process_id}", response_model=ProcessSchema, tags=["LCI"])
async def get_process(process_id: str):
    """Retorna um processo específico pelo ID."""
    p = repository.get_process(process_id)
    if p is None:
        raise HTTPException(status_code=404, detail=f"Processo '{process_id}' não encontrado")
    return ProcessSchema(
        id=p.id, name=p.name, type=p.process_type,
        unit=p.unit, uev=p.uev, description=p.description,
        inputs=[InputSchema(process_id=i.process_id, amount=i.amount)
                for i in p.inputs],
        output_amount=p.output_amount
    )


@app.post("/api/processes", response_model=ProcessSchema, status_code=201, tags=["LCI"])
async def add_process(data: ProcessSchema):
    """Adiciona um novo processo ao repositório LCI."""
    if repository.get_process(data.id):
        raise HTTPException(status_code=409, detail=f"Processo '{data.id}' já existe")

    inputs = [LCIInput(i.process_id, i.amount) for i in data.inputs]

    if data.type == "source":
        process = LCIProcessFactory.create_source(
            data.id, data.name, data.unit, data.uev, data.description
        )
    else:
        process = LCIProcessFactory.create_process(
            data.id, data.name, data.unit, data.uev,
            inputs, data.description, data.output_amount
        )

    repository.add_process(process)
    return data


@app.delete("/api/processes/{process_id}", status_code=204, tags=["LCI"])
async def delete_process(process_id: str):
    """Remove um processo do repositório."""
    if repository.get_process(process_id) is None:
        raise HTTPException(status_code=404, detail=f"Processo '{process_id}' não encontrado")
    repository.remove_process(process_id)


# ── API: Simulação ────────────────────────────────────────────────────────────

@app.post("/api/simulate", response_model=SimulationResponse, tags=["Simulação"])
async def simulate(req: SimulationRequest):
    """
    Executa a simulação de emergia usando o algoritmo DFS do SCALE.

    O parâmetro `minflow` controla a precisão: valores menores aumentam
    a acurácia mas aumentam o tempo de processamento. O valor ótimo
    recomendado por Marvuglia et al. (2013) é 1×10⁻⁶ Msej.
    """
    try:
        simulator.set_strategy(req.strategy)
        result = simulator.run(req.target_process_id, minflow=req.minflow)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    target = repository.get_process(req.target_process_id)
    target_name = target.name if target else req.target_process_id

    contributions = []
    if result.process_results:
        total = result.total_emergy_sej or 1e-30
        for r in sorted(result.process_results.values(),
                        key=lambda x: x.emergy_sej, reverse=True):
            contributions.append({
                "process_id": r.process_id,
                "process_name": r.process_name,
                "emergy_sej": r.emergy_sej,
                "percentage": round(r.emergy_sej / total * 100, 2),
                "uev": r.uev,
                "unit": r.unit,
            })

    return SimulationResponse(
        target_process_id=req.target_process_id,
        target_name=target_name,
        total_emergy_sej=result.total_emergy_sej,
        minflow_threshold=result.minflow_threshold,
        strategy=req.strategy,
        emergy_yield_ratio=_safe(result.emergy_yield_ratio),
        environmental_load_ratio=_safe(result.environmental_load_ratio),
        sustainability_index=_safe(result.sustainability_index),
        renewable_fraction=result.renewable_fraction,
        contributions=contributions,
        formatted_result=simulator.format_result(result)
    )


# ── API: Importar / Exportar ──────────────────────────────────────────────────

@app.get("/api/export", tags=["LCI"])
async def export_lci():
    """Exporta a base LCI atual em formato JSON."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as tmp:
        tmp_path = tmp.name
    repository.save_to_file(tmp_path)
    return FileResponse(
        tmp_path,
        media_type="application/json",
        filename="lci_database.json"
    )


@app.post("/api/import", tags=["LCI"])
async def import_lci(file: UploadFile = File(...)):
    """Importa uma base LCI de um arquivo JSON enviado."""
    if not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Apenas arquivos .json são aceitos")

    with tempfile.NamedTemporaryFile(
        mode="wb", suffix=".json", delete=False
    ) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        repository.load_from_file(tmp_path)
    except (json.JSONDecodeError, KeyError) as e:
        raise HTTPException(status_code=422, detail=f"Arquivo inválido: {e}")
    finally:
        os.unlink(tmp_path)

    return {"message": f"Importados {len(repository.get_all_processes())} processos com sucesso"}


@app.get("/api/validate", tags=["LCI"])
async def validate_repository():
    """Valida a consistência da base LCI e retorna erros encontrados."""
    errors = repository.validate()
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "process_count": len(repository.get_all_processes())
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
