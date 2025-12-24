# Sistema de Apontamento de Horas (Timesheet)

Sistema web desenvolvido em **Python/Django** para gestão de produtividade e controle de horas em atividades operacionais da empresa. O projeto foca na experiência do usuário, priorizando uma interface amigável e na integridade dos dados, substituindo planilhas manuais por um fluxo digital e responsivo com controle de acesso granular.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Django](https://img.shields.io/badge/Django-5.0-green)
![TailwindCSS](https://img.shields.io/badge/Tailwind-CSS-38bdf8)

## Funcionalidades Principais

### 🚀 Gestão Operacional
* **Apontamento Flexível:** Registro de horas vinculado a **Obra Específica** (com adendo) ou **Código de Cliente Geral** (para setores que não tem informações de adendo), garantindo rastreabilidade de custos.
* **Gestão de Veículos:** Seleção de frota cadastrada ou cadastro rápido de veículos externos/alugados durante o apontamento.
* **Equipes Dinâmicas:** Adição de múltiplos auxiliares (Auxiliares/Oficiais) em um único registro de ponto.
* **Início da Jornada** Registro do local de início da jornada para conciliação com ponto eletrônico para cálculo de deslocamento.
* **Histórico Detalhado:** Visualização inteligente que "explode" os registros, mostrando separadamente o colaborador principal e seus auxiliares.

### 📋 Folha e Financeiro
* **Indicadores de Folha:** Checkboxes específicos para sinalizar **Plantão** e **Pernoite/Diária** (com data específica), agilizando o fechamento mensal.
* **Workflow de Ajustes:** Fluxo de solicitação de correção onde o colaborador justifica o erro e o gestor aprova ou rejeita, mantendo histórico auditável.
* **Exportação Avançada (Excel):** Geração de relatórios `.xlsx` consolidados, com cálculo automático de horas (incluindo virada de noite) e separação de custos por centro/obra.

### 🎨 Experiência do Usuário (UX)
* **Calendário Visual:** Visualização mensal com indicadores de status (Pendente/Preenchido) e ícones para dias com pernoite.
* **Interface Responsiva:** Design *Mobile-First* com Dark Mode nativo utilizando TailwindCSS.
* **Feedback Imediato:** Modais de confirmação e validação de conflitos de horário (Overlap) em tempo real.

## Controle de Acesso e Permissões (RBAC)

O sistema implementa uma hierarquia de acesso robusta para garantir a segurança e organização dos dados:

* **OWNER (Superusuário):** Acesso irrestrito. Visualiza histórico global, gerencia cadastros, aprova ajustes e exporta relatórios financeiros.
* **ADMINISTRATIVO:** Visualiza e gerencia colaboradores pertencentes aos **"Setores sob Gestão"**, além de seus próprios registros.
* **GESTOR:** Envia formulários apenas para si, mas possui visão gerencial (leitura) sobre sua equipe.
* **OPERACIONAL:** Acesso restrito. Pode apenas registrar e visualizar seu próprio histórico.

## Visão de Futuro & Roadmap

Este projeto é o alicerce (MVP) para um ecossistema maior de gestão de obras. Os próximos passos estratégicos incluem:

1.  **Mobile First:** Desenvolvimento de PWA ou App Nativo para uso offline em obras sem sinal.
2.  **Integração com Cronogramas:** Vínculo direto entre as horas apontadas e o cronograma físico da obra (MS Project).
3.  **Dashboard em Tempo Real:** Visualização do avanço físico x financeiro.
4.  **Inteligência de Dados:** Análise de métricas para refinar orçamentos futuros (Orçado vs. Realizado).

## Tecnologias Utilizadas

* **Backend:** Python 3, Django 5
* **Frontend:** HTML5, TailwindCSS (CDN), JavaScript Moderno
* **Bibliotecas:** * `Select2` (Selects pesquisáveis via AJAX)
    * `OpenPyXL` (Geração de relatórios Excel)
* **Banco de Dados:** SQLite (Desenvolvimento)

## Como Executar o Projeto

1. **Clone o repositório:**
   ```bash
   git clone [https://github.com/GFerreira019/sistema-gestao-obras.git](https://github.com/GFerreira019/sistema-gestao-obras.git)
   cd sistema-gestao-obras

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
