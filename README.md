# 🌞 SCALE Emergy Calculator

Sistema web para cálculo de emergia baseado em Inventários do Ciclo de Vida (LCI), inspirado no software SCALE (Marvuglia et al., 2013).

Desenvolvido como Atividade Prática Supervisionada (APS) da disciplina de **Engenharia de Software** — UNIP, campus Chácara II, 1º semestre de 2026.

---

## Sobre o projeto

A **emergia** representa a quantidade total de energia solar necessária para produzir um bem ou serviço, medida em solar emjoules (sej). Este sistema permite modelar processos industriais como grafos de dependência e calcular automaticamente a emergia de qualquer processo-alvo, além de gerar índices de sustentabilidade ambiental.

### Módulos implementados

| Módulo | Descrição | Padrão de Projeto |
|--------|-----------|-------------------|
| **LCI Manager** | CRUD de processos, persistência JSON, validação | Factory |
| **Emergy Calculator** | Algoritmo DFS, álgebra emergética, índices EYR/ELR/ESI | Strategy |
| **Notificações** | Eventos entre camadas desacopladas | Observer |
| **API REST** | 8 endpoints com documentação Swagger automática | — |
| **Frontend Web** | Interface Bootstrap 5 + Chart.js | — |

### Algoritmo DFS (baseado no SCALE)

O sistema percorre o grafo de processos em profundidade a partir do processo-alvo, acumulando contribuições de emergia de cada fonte primária. Implementa as **4 regras da Álgebra Emergética de Odum (1996)**:

1. Co-produtos recebem a emergia total do processo
2. Divisões são proporcionais ao fluxo físico
3. Sem dupla contagem em retroalimentações (detecção de ciclos)
4. Materiais reciclados pelo caminho de maior emergia

### Índices emergéticos calculados

| Índice | Fórmula | Interpretação |
|--------|---------|---------------|
| **EYR** | (R + N + F) / F | Eficiência de geração de valor |
| **ELR** | (N + F) / R | Pressão sobre o meio ambiente |
| **ESI** | EYR / ELR | Sustentabilidade geral (> 1 = sustentável) |

---

## Tecnologias

- **Backend:** Python 3.11+, FastAPI, Uvicorn, Pydantic
- **Frontend:** HTML5, Bootstrap 5, JavaScript, Chart.js
- **Testes:** pytest (47 testes — unitários, integração e API)
- **Documentação:** OpenAPI / Swagger UI automático

---

## Como executar

### 1. Clone o repositório

```bash
git clone https://github.com/murilo-simoes/scale-emergy-calculator.git
cd scale-emergy-calculator
```

### 2. Instale as dependências

```bash
pip install -r requirements.txt
```

### 3. Inicie o servidor

```bash
python app.py
```

### 4. Acesse no navegador

| URL | Descrição |
|-----|-----------|
| `http://localhost:8000` | Interface web principal |
| `http://localhost:8000/docs` | Documentação interativa da API (Swagger) |

---

## Estrutura do projeto

```
scale-emergy-calculator/
├── app.py                        # API REST FastAPI (ponto de entrada)
├── requirements.txt              # Dependências Python
├── modules/
│   ├── lci_manager.py            # Gerenciamento LCI + padrão Factory
│   ├── emergy_calculator.py      # Simulador DFS + padrão Strategy
│   └── observer.py               # Padrão Observer
├── templates/
│   └── index.html                # Interface web
├── static/
│   ├── css/style.css
│   └── js/app.js
├── tests/
│   ├── test_lci_manager.py       # 17 testes unitários
│   ├── test_emergy_calculator.py # 15 testes unitários
│   └── test_api.py               # 15 testes de integração
└── data/
    └── sample_lci.json           # Base LCI de exemplo (8 processos)
```

---

## Executar testes

```bash
pytest tests/ -v
```

---

## Endpoints da API

| Método | Endpoint | Descrição |
|--------|----------|-----------|
| `GET` | `/api/processes` | Lista todos os processos LCI |
| `POST` | `/api/processes` | Adiciona novo processo |
| `DELETE` | `/api/processes/{id}` | Remove processo |
| `POST` | `/api/simulate` | Executa simulação de emergia |
| `GET` | `/api/export` | Exporta base LCI em JSON |
| `POST` | `/api/import` | Importa base LCI de JSON |
| `GET` | `/api/validate` | Valida consistência do repositório |

---

## Grupo

| Nome | RA |
|------|----|
| Murilo Rodrigues Simões | F350100 |
| Bruno Victor Costa dos Santos | G735374 |
| Natan de Matos Souza | F3512A7 |
| Gabriela Dias Silveira | N086AE2 |
| Marcos Barreto Alves | F355535 |

**UNIP — Ciência da Computação — Campus Chácara II — 1º Semestre 2026**

---

## Referências

- MARVUGLIA, A. et al. SCALE: A software for calculating emergy based on life cycle inventories. *Ecological Modelling*, v. 248, p. 80-91, 2013.
- ARBAULT, D. et al. Emergy evaluation using the calculation software SCALE. *Science of the Total Environment*, v. 472, p. 608-619, 2014.
- VALYI, I.; ORTEGA, E. Emergy simulator, an open source simulation platform. *Emergy Synthesis 3*, 2004.
- ZHAO, Y.; XU, J.; YU, Y. Emergy accounting for embodied carbon in China's construction industry. *Ecological Indicators*, v. 158, 2024.
- FIELDING, R. T. Architectural styles and the design of network-based software architectures. 2000. Tese (Doutorado) — University of California, Irvine, 2000.
- ODUM, H. T. Environmental accounting: emergy and environmental decision making. New York: John Wiley & Sons, 1996

