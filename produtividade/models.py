from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from datetime import date, datetime, timedelta

# ==============================================================================
# TABELAS AUXILIARES (CADASTROS)
# ==============================================================================

class Setor(models.Model):
    """
    Cadastro de departamentos/setores para controle de lotação e permissões de acesso.
    """
    nome = models.CharField(
        max_length=100, 
        unique=True, 
        verbose_name="Nome do Setor"
    )
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Setor da Empresa"
        verbose_name_plural = "Setores da Empresa"
        ordering = ['nome']

    def __str__(self):
        return self.nome


class CentroCusto(models.Model):
    """
    Entidade para alocação de custos e justificativas operacionais.
    """
    nome = models.CharField(
        max_length=100, 
        unique=True, 
        verbose_name="Nome do Centro de Custo / Justificativa"
    )
    
    permite_alocacao = models.BooleanField(
        default=False,
        verbose_name="Permite alocar em Obra/Cliente?",
        help_text="Se marcado, ao selecionar este item, será solicitado o Código da Obra ou Cliente."
    )
    
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Centro de Custo / Justificativa"
        verbose_name_plural = "Centros de Custo / Justificativas"
        ordering = ['nome']

    def __str__(self):
        return self.nome


class Projeto(models.Model):
    """
    Cadastro centralizado de Obras e Projetos ativos da empresa.
    """
    codigo = models.CharField(
        max_length=50, 
        unique=True, 
        verbose_name="Código da Obra", 
        null=True, 
        blank=True
    )
    nome = models.CharField(
        max_length=255, 
        verbose_name="Nome do Projeto"
    )
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Projeto/Obra"
        verbose_name_plural = "Projetos/Obras"
        ordering = ['codigo']

    def __str__(self):
        return f"{self.codigo} - {self.nome}"


class CodigoCliente(models.Model):
    """
    Cadastro de Códigos Gerais de Cliente padronizados com 4 dígitos.
    """
    codigo = models.CharField(
        max_length=4, 
        unique=True, 
        verbose_name="Cód. Cliente (4 Dígitos)",
        validators=[RegexValidator(
            regex=r'^\d{4}$', 
            message='O código deve ter exatamente 4 dígitos numéricos.'
        )]
    )
    nome = models.CharField(
        max_length=255, 
        verbose_name="Nome do Cliente"
    )
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Código do Cliente"
        verbose_name_plural = "Códigos de Cliente"
        ordering = ['codigo']

    def __str__(self):
        return f"{self.codigo} - {self.nome}"


class Colaborador(models.Model):
    """
    Entidade que estende o Usuário do Django para regras de negócio.
    """
    id_colaborador = models.CharField(
        max_length=50, 
        unique=True, 
        verbose_name="ID Colaborador"
    )
    nome_completo = models.CharField(max_length=255)
    cargo = models.CharField(max_length=100, default='Operador')
    
    user_account = models.OneToOneField(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Conta de Usuário (Login)"
    )
    
    setor = models.ForeignKey(
        Setor, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Setor de Alocação"
    )

    setores_gerenciados = models.ManyToManyField(
        Setor,
        blank=True,
        related_name='gestores',
        verbose_name="Setores sob Gestão (Visão Admin/Gestor)"
    )

    class Meta:
        verbose_name = "Colaborador"
        verbose_name_plural = "Colaboradores"
        ordering = ['nome_completo']

    def __str__(self):
        return f"{self.nome_completo}"


class Veiculo(models.Model):
    """
    Cadastro da frota oficial e veículos de apoio da empresa.
    """
    placa = models.CharField(
        max_length=10, 
        unique=True, 
        verbose_name="Placa"
    )
    descricao = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        verbose_name="Modelo/Descrição"
    )

    class Meta:
        verbose_name = "Veículo"
        verbose_name_plural = "Veículos"

    def __str__(self):
        if self.descricao:
            return f"{self.descricao} - {self.placa}"
        return self.placa


# ==============================================================================
# TABELA PRINCIPAL (CORE)
# ==============================================================================

class Apontamento(models.Model):
    """
    Registro principal de Timesheet.
    """
    
    LOCAL_CHOICES = [
        ('INT', 'Dentro da obra'), 
        ('EXT', 'Fora da obra')
    ]
    
    STATUS_APROVACAO_CHOICES = [
        ('EM_ANALISE', 'Em Análise'),
        ('APROVADO', 'Aprovado'),
        ('REJEITADO', 'Rejeitado'),
        ('SOLICITACAO_AJUSTE', 'Solicitação de Ajuste'),
    ]

    # --- 1. Identificação e Tempo ---
    colaborador = models.ForeignKey(
        Colaborador, 
        on_delete=models.PROTECT, 
        verbose_name="Colaborador"
    )
    data_apontamento = models.DateField(
        default=timezone.now, 
        verbose_name="Data"
    )
    hora_inicio = models.TimeField(verbose_name="Hora Início")
    hora_termino = models.TimeField(verbose_name="Hora Término")
    
    # --- 2. Localização e Contexto ---
    local_execucao = models.CharField(
        max_length=3, 
        choices=LOCAL_CHOICES, 
        default='INT', 
        verbose_name="Local de Execução"
    )
    
    projeto = models.ForeignKey(
        Projeto, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Projeto"
    )

    codigo_cliente = models.ForeignKey(
        CodigoCliente, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Código do Cliente"
    )

    centro_custo = models.ForeignKey(
        CentroCusto, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Setor / Justificativa (Custo)"
    ) 

    # --- 3. Gestão de Veículos (Híbrida) ---
    veiculo = models.ForeignKey(
        Veiculo, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Veículo Cadastrado"
    )
    veiculo_manual_modelo = models.CharField(
        max_length=100, blank=True, null=True, verbose_name="Modelo (Manual)"
    )
    veiculo_manual_placa = models.CharField(
        max_length=20, blank=True, null=True, verbose_name="Placa (Manual)"
    )
    
    # --- 4. Equipe e Ocorrências ---
    ocorrencias = models.TextField(
        blank=True, null=True, verbose_name="Ocorrências / Obs."
    )
    
    auxiliar = models.ForeignKey(
        Colaborador, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='apontamentos_auxiliados'
    )
    auxiliares_extras = models.ManyToManyField(
        Colaborador,
        blank=True,
        related_name='apontamentos_como_extra',
        verbose_name="Auxiliares Extras"
    )

    # --- 5. Adicionais de Folha ---
    em_plantao = models.BooleanField(
        default=False, 
        verbose_name="Atividade em Plantão?"
    )
    data_plantao = models.DateField(
        null=True, 
        blank=True, 
        verbose_name="Data do Plantão"
    )
    dorme_fora = models.BooleanField(
        default=False, 
        verbose_name="Dorme Fora Nesta Data?"
    )
    data_dorme_fora = models.DateField(
        null=True, 
        blank=True, 
        verbose_name="Data do Dorme-Fora"
    )

    # --- 6. Auditoria (Criação) ---
    registrado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Usuário de Registro"
    )
    data_registro = models.DateTimeField(auto_now_add=True)

    # --- 7. Controle de Ajustes e Workflow ---
    id_agrupamento = models.CharField(
        max_length=100, 
        null=True, 
        blank=True, 
        verbose_name="ID de Agrupamento (Rateio)"
    )

    motivo_ajuste = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Motivo do Ajuste (Solicitação)"
    )
    
    status_aprovacao = models.CharField(
        max_length=20,
        choices=STATUS_APROVACAO_CHOICES,
        default='EM_ANALISE',
        verbose_name="Status Workflow"
    )

    status_ajuste = models.CharField(
        max_length=20,
        choices=[('PENDENTE', 'Pendente'), ('APROVADO', 'Aprovado')],
        null=True,
        blank=True,
        verbose_name="Status da Solicitação (Legado)"
    )

    contagem_edicao = models.IntegerField(
        default=0,
        verbose_name="Qtd. Edições Realizadas"
    )
    
    motivo_rejeicao = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Motivo da Rejeição (Gerente)"
    )

    # --- 8. Geolocalização ---
    latitude = models.DecimalField(
        max_digits=12,
        decimal_places=8, 
        null=True, 
        blank=True, 
        verbose_name="Latitude"
    )
    longitude = models.DecimalField(
        max_digits=12, 
        decimal_places=8, 
        null=True, 
        blank=True, 
        verbose_name="Longitude"
    )

    @property
    def duracao_total_str(self):
        """Calcula a duração formatada HH:MM considerando virada de dia"""
        if not self.hora_inicio or not self.hora_termino:
            return "00:00"
        
        d = date(2000, 1, 1)
        dt_ini = datetime.combine(d, self.hora_inicio)
        dt_fim = datetime.combine(d, self.hora_termino)
        
        if dt_fim < dt_ini:
            dt_fim += timedelta(days=1)
            
        diff = dt_fim - dt_ini
        total_seconds = int(diff.total_seconds())
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        return f"{h:02d}:{m:02d}"

    class Meta:
        verbose_name = "Apontamento"
        verbose_name_plural = "Apontamentos"
        ordering = ['-data_apontamento', '-id']

    def __str__(self):
        return f"{self.colaborador} - {self.data_apontamento}"


# ==============================================================================
# TABELAS DE HISTÓRICO E AUDITORIA
# ==============================================================================

class ApontamentoHistorico(models.Model):
    """
    Armazena o estado anterior de um apontamento antes de ser editado.
    Permite que o Gerente compare a versão original com a editada.
    """
    apontamento_original = models.ForeignKey(
        Apontamento,
        on_delete=models.CASCADE,
        related_name='historico_versoes',
        verbose_name="Apontamento Original"
    )
    
    dados_snapshot = models.JSONField(
        verbose_name="Cópia dos Dados (Snapshot)"
    )
    
    editado_por = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Editado Por"
    )
    
    data_edicao = models.DateTimeField(auto_now_add=True)
    
    numero_edicao = models.IntegerField(
        verbose_name="Versão da Edição"
    )

    class Meta:
        verbose_name = "Histórico de Alteração"
        verbose_name_plural = "Históricos de Alterações"
        ordering = ['-data_edicao']

    def __str__(self):
        return f"V{self.numero_edicao} - {self.apontamento_original}"