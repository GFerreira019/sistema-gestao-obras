from django.contrib import admin
from .models import Projeto, Colaborador, Veiculo, Apontamento, Setor, CodigoCliente

# ==============================================================================
# CADASTROS AUXILIARES
# Tabelas de apoio para o funcionamento do sistema (Obras, Pessoas, Ativos)
# ==============================================================================

@admin.register(Setor)
class SetorAdmin(admin.ModelAdmin):
    """Gerenciamento de Setores/Departamentos (ex: Oficina, ADM)."""
    list_display = ('nome', 'ativo')
    search_fields = ('nome',)


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
    Permite vincular o colaborador à conta de usuário (login) e definir seu setor de alocação.
    """
    list_display = ('id_colaborador', 'nome_completo', 'cargo', 'setor', 'user_account')
    search_fields = ('nome_completo', 'id_colaborador')
    list_filter = ('cargo', 'setor')
    
    # Adicionado 'setores_gerenciados' para permitir a configuração de gestores/admins
    fields = ('id_colaborador', 'nome_completo', 'cargo', 'setor', 'setores_gerenciados', 'user_account')
    
    # Cria uma interface visual melhor para selecionar múltiplos setores
    filter_horizontal = ('setores_gerenciados',)


@admin.register(Veiculo)
class VeiculoAdmin(admin.ModelAdmin):
    """Cadastro da frota de veículos."""
    list_display = ('placa', 'descricao')
    search_fields = ('placa', 'descricao')


# ==============================================================================
# REGISTRO PRINCIPAL (CORE)
# Tabela onde ficam armazenados os apontamentos de horas
# ==============================================================================

@admin.register(Apontamento)
class ApontamentoAdmin(admin.ModelAdmin):
    """
    Visão geral dos apontamentos de produtividade.
    Exibe colunas dinâmicas para exibir o local (Obra ou Setor) e o status do registro.
    """
    list_display = (
        'data_apontamento',
        'colaborador',
        'get_tipo_local',       # Método customizado
        'get_detalhe_local',    # Método customizado
        'hora_inicio',
        'hora_termino'
    )

    list_filter = (
        'data_apontamento',
        'local_execucao',       # Filtra por Dentro/Fora da obra
        'projeto',
        'codigo_cliente',
        'setor',
        'colaborador'
    )

    # Permite pesquisar pelo nome do colaborador, obra ou setor
    search_fields = (
        'colaborador__nome_completo',
        'projeto__nome',
        'codigo_cliente__nome',
        'setor__nome'
    )

    # --- Métodos Personalizados para Listagem ---

    def get_tipo_local(self, obj):
        """Retorna a descrição legível do local (Dentro/Fora)."""
        return obj.get_local_execucao_display()
    get_tipo_local.short_description = "Tipo"

    def get_detalhe_local(self, obj):
        if obj.local_execucao == 'INT':
            if obj.projeto:
                return f"Obra: {obj.projeto}"
            elif obj.codigo_cliente:
                return f"Cli: {obj.codigo_cliente}"
            return "—"
        elif obj.local_execucao == 'EXT':
            return obj.setor if obj.setor else "—"
        return "—"
    get_detalhe_local.short_description = "Obra / Cliente / Setor"