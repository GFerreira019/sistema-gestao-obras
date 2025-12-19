from django.contrib import admin
from .models import Projeto, Colaborador, Veiculo, Apontamento, Setor, CodigoCliente, CentroCusto

# ==============================================================================
# CADASTROS AUXILIARES
# Tabelas de apoio para o funcionamento do sistema (Obras, Pessoas, Ativos)
# ==============================================================================

@admin.register(Setor)
class SetorAdmin(admin.ModelAdmin):
    """Gerenciamento de Setores/Departamentos (ex: Manutenção, E&O)."""
    list_display = ('nome', 'ativo')
    search_fields = ('nome',)


@admin.register(CentroCusto)
class CentroCustoAdmin(admin.ModelAdmin):
    """Gerenciamento de Centros de Custo / Justificativas para alocação externa."""
    # Exibe a coluna booleana para fácil visualização
    list_display = ('nome', 'permite_alocacao', 'ativo')
    search_fields = ('nome',)
    list_filter = ('ativo', 'permite_alocacao')


@admin.register(Projeto)
class ProjetoAdmin(admin.ModelAdmin):
    """Gerenciamento de Obras e Projetos."""
    list_display = ('codigo', 'nome', 'ativo')
    search_fields = ('codigo', 'nome')
    list_filter = ('ativo',)


@admin.register(CodigoCliente)
class CodigoClienteAdmin(admin.ModelAdmin):
    """Gerenciamento de Códigos de Cliente (4 dígitos)."""
    list_display = ('codigo', 'nome', 'ativo')
    search_fields = ('codigo', 'nome')
    list_filter = ('ativo',)


@admin.register(Colaborador)
class ColaboradorAdmin(admin.ModelAdmin):
    """
    Cadastro de funcionários e prestadores de serviço. 
    Permite vincular o colaborador à conta de usuário e definir setores gerenciados.
    """
    list_display = ('id_colaborador', 'nome_completo', 'cargo', 'setor', 'user_account')
    search_fields = ('nome_completo', 'id_colaborador')
    list_filter = ('cargo', 'setor')
    
    fields = ('id_colaborador', 'nome_completo', 'cargo', 'setor', 'setores_gerenciados', 'user_account')
    
    # Cria uma interface visual melhor para selecionar múltiplos setores gerenciados
    filter_horizontal = ('setores_gerenciados',)


@admin.register(Veiculo)
class VeiculoAdmin(admin.ModelAdmin):
    """Cadastro da frota de veículos oficiais ou alugados."""
    list_display = ('placa', 'descricao')
    search_fields = ('placa', 'descricao')


# ==============================================================================
# REGISTRO PRINCIPAL (CORE)
# Tabela onde ficam armazenados os apontamentos de horas e produtividade
# ==============================================================================

@admin.register(Apontamento)
class ApontamentoAdmin(admin.ModelAdmin):
    """
    Visão geral dos apontamentos de produtividade.
    Exibe colunas dinâmicas para exibir o local e detalhamento de alocação de custos.
    """
    list_display = (
        'data_apontamento',
        'colaborador',
        'get_tipo_local',
        'get_detalhe_local',
        'hora_inicio',
        'hora_termino'
    )

    list_filter = (
        'data_apontamento',
        'local_execucao',
        'projeto',
        'codigo_cliente',
        'centro_custo',
        'colaborador'
    )

    # Permite pesquisar pelo nome do colaborador, obra, cliente ou centro de custo
    search_fields = (
        'colaborador__nome_completo',
        'projeto__nome',
        'codigo_cliente__nome',
        'centro_custo__nome'    
    )

    # --- Métodos Personalizados para Listagem ---

    def get_tipo_local(self, obj):
        """Retorna a descrição legível do local de execução."""
        return obj.get_local_execucao_display()
    get_tipo_local.short_description = "Tipo"

    def get_detalhe_local(self, obj):
        """Lógica dinâmica para exibir o local específico ou Centro de Custo com alocação."""
        if obj.local_execucao == 'INT':
            if obj.projeto:
                return f"Obra: {obj.projeto}"
            elif obj.codigo_cliente:
                return f"Cli: {obj.codigo_cliente}"
            return "—"
        elif obj.local_execucao == 'EXT':
            # Se for externo mas tiver obra alocada, mostra a justificativa + obra/cliente
            base = str(obj.centro_custo) if obj.centro_custo else "—"
            if obj.projeto:
                return f"{base} -> Obra: {obj.projeto.codigo}"
            elif obj.codigo_cliente:
                return f"{base} -> Cli: {obj.codigo_cliente.codigo}"
            return base
        return "—"
    get_detalhe_local.short_description = "Local / Detalhe"