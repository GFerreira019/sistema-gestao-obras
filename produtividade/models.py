from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.core.validators import RegexValidator

# ==============================================================================
# TABELAS AUXILIARES (CADASTROS)
# ==============================================================================

class Setor(models.Model):
    """Cadastro de departamentos/setores (ex: Oficina, ADM)."""
    nome = models.CharField(
        max_length=100, 
        unique=True, 
        verbose_name="Nome do Setor")
    ativo = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Setor"
        verbose_name_plural = "Setores"
        ordering = ['nome']

    def __str__(self):
        return self.nome


class Projeto(models.Model):
    """Cadastro de Obras e Projetos da empresa."""
    codigo = models.CharField(
        max_length=50, 
        unique=True, 
        verbose_name="Código da Obra", 
        null=True, 
        blank=True)
    nome = models.CharField(
        max_length=255, 
        verbose_name="Nome do Projeto")
    ativo = models.BooleanField(
        default=True)

    class Meta:
        verbose_name = "Projeto/Obra"
        verbose_name_plural = "Projetos/Obras"
        ordering = ['codigo']

    def __str__(self):
        return f"{self.codigo} - {self.nome}"


class CodigoCliente(models.Model):
    """Cadastro de Códigos Gerais de Cliente (4 Dígitos)."""
    codigo = models.CharField(
        max_length=4, 
        unique=True, 
        verbose_name="Cód. Cliente (4 Dígitos)",
        validators=[RegexValidator(
            regex=r'^\d{4}$', 
            message='O código deve ter exatamente 4 dígitos numéricos.')]
    )
    nome = models.CharField(
        max_length=255, 
        verbose_name="Nome do Cliente")
    ativo = models.BooleanField(
        default=True)

    class Meta:
        verbose_name = "Código do Cliente"
        verbose_name_plural = "Códigos de Cliente"
        ordering = ['codigo']

    def __str__(self):
        return f"{self.codigo} - {self.nome}"


class Colaborador(models.Model):
    """
    Cadastro de funcionários e prestadores de serviço.
    Associa a entidade de negócio ao Usuário Django para controle de acesso.
    """
    id_colaborador = models.CharField(
        max_length=50, 
        unique=True, 
        verbose_name="ID Colaborador")
    nome_completo = models.CharField(
        max_length=255)
    cargo = models.CharField(
        max_length=100, 
        default='Operador')
    
    # --- RBAC e Associação ---
    user_account = models.OneToOneField(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Conta de Usuário (Login)"
    )
    
    # Setor onde o colaborador trabalha (Lotação)
    setor = models.ForeignKey(
        Setor, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Setor de Alocação"
    )

    # === NOVO CAMPO: Para ADMINISTRATIVO e GESTOR ===
    # Define quais setores este usuário pode visualizar/gerenciar
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
        return f"{self.nome_completo} ({self.cargo})"


class Veiculo(models.Model):
    """Cadastro da frota oficial da empresa."""
    placa = models.CharField(
        max_length=10, 
        unique=True, 
        verbose_name="Placa")
    descricao = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        verbose_name="Modelo/Descrição")

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
    Registro diário de horas trabalhadas (Timesheet).
    Centraliza informações de colaborador, local, horários e recursos utilizados.
    """
    
    # --- Constantes de Escolha ---
    LOCAL_CHOICES = [
        ('INT', 'Dentro da obra'), 
        ('EXT', 'Fora da obra')
    ]
    
    TANGERINO_CHOICES = [
        ('OUT', 'Outros'), 
        ('RES', 'Residência'), 
        ('CLI', 'Cliente'), 
        ('SED', 'Sede ATGB')
    ]

    # --- 1. Identificação Básica ---
    colaborador = models.ForeignKey(
        Colaborador, 
        on_delete=models.PROTECT, 
        verbose_name="Colaborador")
    data_apontamento = models.DateField(
        default=timezone.now, 
        verbose_name="Data")
    local_execucao = models.CharField(
        max_length=3, 
        choices=LOCAL_CHOICES, 
        default='INT', 
        verbose_name="Local de Execução"
    )
    
    # --- 2. Gestão de Veículos (Híbrida) ---
    veiculo = models.ForeignKey(
        Veiculo, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Veículo Cadastrado"
    )
    veiculo_manual_modelo = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        verbose_name="Modelo (Manual)")
    veiculo_manual_placa = models.CharField(
        max_length=20, 
        blank=True, 
        null=True, 
        verbose_name="Placa (Manual)")

    # --- 3. Contexto do Trabalho (Condicional) ---
    projeto = models.ForeignKey(
        Projeto, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Projeto")

    codigo_cliente = models.ForeignKey(
        CodigoCliente, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Código do Cliente"
    )

    local_inicio_jornada = models.CharField(
        max_length=3, 
        choices=TANGERINO_CHOICES, 
        null=True, 
        blank=True, 
        verbose_name="Início Jornada"
    )
    local_inicio_jornada_outros = models.CharField(
        max_length=100, 
        blank=True, 
        null=True, 
        verbose_name="Detalhe Outros")
    
    # O Setor só é gravado aqui para saber o local do apontamento EXT.
    setor = models.ForeignKey(
        Setor, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Setor Apontado (Fora)") 

    # --- 4. Detalhes do Apontamento ---
    hora_inicio = models.TimeField(
        verbose_name="Hora Início")
    hora_termino = models.TimeField(
        verbose_name="Hora Término")
    ocorrencias = models.TextField(
        blank=True, 
        null=True, 
        verbose_name="Ocorrências / Obs.")
    
    # --- 5. Recursos Adicionais (Equipe) ---
    auxiliar = models.ForeignKey(
        Colaborador, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='apontamentos_auxiliados'
    )
    auxiliares_extras_ids = models.CharField(
        max_length=255, 
        blank=True, 
        null=True)

    # --- 6. Metadados de Auditoria ---
    registrado_por = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        verbose_name="Usuário de Registro")
    data_registro = models.DateTimeField(
        auto_now_add=True)

    class Meta:
        verbose_name = "Apontamento"
        verbose_name_plural = "Apontamentos"
        ordering = ['-data_apontamento', '-id']

    def __str__(self):
        return f"{self.colaborador} - {self.data_apontamento}"