from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError

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
        verbose_name = "Setor (Acesso/Lotação)"
        verbose_name_plural = "Setores (Acesso/Lotação)"
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

    # --- 6. Auditoria ---
    registrado_por = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Usuário de Registro"
    )
    data_registro = models.DateTimeField(auto_now_add=True)

    # --- 7. Controle de Ajustes (Solicitações) ---
    motivo_ajuste = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Motivo do Ajuste"
    )
    
    STATUS_AJUSTE_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('APROVADO', 'Aprovado'),
    ]
    
    status_ajuste = models.CharField(
        max_length=20,
        choices=STATUS_AJUSTE_CHOICES,
        null=True,
        blank=True,
        verbose_name="Status da Solicitação"
    )

    class Meta:
        verbose_name = "Apontamento"
        verbose_name_plural = "Apontamentos"
        ordering = ['-data_apontamento', '-id']

    def __str__(self):
        return f"{self.colaborador} - {self.data_apontamento}"