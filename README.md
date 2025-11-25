# Sistema de Apontamento de Horas (Timesheet)

Sistema web desenvolvido em **Python/Django** para gestão de produtividade e controle de horas em atividades operacionais da empresa. O projeto foca na experiência do usuário, focando em uma interface amigável e na integridade dos dados, substituindo planilhas manuais por um fluxo digital e responsivo.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Django](https://img.shields.io/badge/Django-5.0-green)
![TailwindCSS](https://img.shields.io/badge/Tailwind-CSS-38bdf8)

## Funcionalidades Principais

* **Apontamento Híbrido:** Registro de horas para colaboradores **Dentro da Obra** (vinculado a projetos) ou **Fora da Obra** (vinculado a setores/justificativas).
* **Gestão de Veículos:** Seleção de frota cadastrada ou cadastro rápido de veículos externos/alugados durante o apontamento.
* **Equipes Dinâmicas:** Adição de múltiplos auxiliares (Ajudantes/Oficiais) em um único registro de ponto.
* **Integração Visual Tangerino:** Registro do local de início da jornada para conciliação com ponto eletrônico.
* **Histórico Detalhado:** Visualização inteligente que "explode" os registros, mostrando separadamente o colaborador principal e seus auxiliares.
* **UX Aprimorada:**
    * Autocomplete em campos de seleção (Select2).
    * Modal de Feedback com resumo antes do envio.
    * Layout responsivo e Dark Mode nativo.


## Visão de Futuro & Roadmap

Este projeto é o alicerce (MVP) para um ecossistema maior de gestão de obras. Os próximos passos estratégicos incluem:

1.  **Mobile First:** Desenvolvimento de PWA ou App Nativo para uso offline em obras sem sinal.
2.  **Integração com Cronogramas:** Vínculo direto entre as horas apontadas e o cronograma físico da obra (MS Project).
3.  **Dashboard em Tempo Real:** Visualização do avanço físico x financeiro.
4.  **Inteligência de Dados:** Análise de métricas para refinar orçamentos futuros (Orçado vs. Realizado).


## 🛠️ Tecnologias Utilizadas

* **Backend:** Python, Django 5
* **Frontend:** HTML5, TailwindCSS (via CDN), JavaScript (Vanilla + jQuery)
* **Bibliotecas JS:** Select2 (para caixas de seleção pesquisáveis)
* **Banco de Dados:** SQLite (Desenvolvimento)


## Como Executar o Projeto

1. **Clone o repositório:**
    ```bash
   git clone [https://github.com/SEU-USUARIO/sistema-apontamento-obras.git](https://github.com/SEU-USUARIO/sistema-apontamento-obras.git)
   cd sistema-apontamento-obras

2. **Crie e ative um ambiente virtual:**
    ```bash
    python -m venv venv
    # Windows:
    venv\Scripts\activate
    # Linux/Mac:
    source venv/bin/activate

3. **Instale as dependências:**
    ```bash
    pip install -r requirements.txt

4. **Configure o Banco de Dados:**
    ```bash
    python manage.py makemigrations
    python manage.py migrate

5. **Crie um Superusuário (Admin):**
    ```bash
    python manage.py createsuperuser

6. **Inicie o Servidor:**
    ```bash
    python manage.py runserver


Acesse: http://127.0.0.1:8000