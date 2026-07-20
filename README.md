# 🛡️ ART Check

Aplicativo web para análise, identificação de inconsistências e edição de **ART (Análise de Risco de Tarefa)**, construído com [Streamlit](https://streamlit.io/).

## Funcionalidades

- 📊 Painel geral com estatísticas e resumo das análises
- 📋 Visualização e edição dos dados da planilha
- 🔍 Validação da classificação de risco (com correção assistida)
- 🔄 Detecção de ARTs duplicadas e quase idênticas
- ⚠️ Consistência entre TAREFA, ITEM e PASSO
- 🎯 Análise de medidas de controle por risco/causa
- 🔂 Identificação de riscos, causas e controles constantes
- 📌 Títulos divergentes e campos vazios

Os dados são processados **apenas na memória da sessão** — nenhuma planilha enviada é armazenada no servidor.

## Uso online

O app está publicado no Streamlit Community Cloud. Basta acessar a URL, carregar uma planilha `.xlsx` exportada do sistema de ARTs pela barra lateral e navegar pelas análises.

## Executar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Estrutura

| Arquivo | Descrição |
|---------|-----------|
| `app.py` | Interface Streamlit |
| `analysis.py` | Funções de análise e checagem dos dados |
| `requirements.txt` | Dependências |
| `.streamlit/config.toml` | Tema da aplicação |

---

Produzido por Leonardo Manzoli Stoco — Limpeza Industrial, Porto de Tubarão.
