from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash


db = SQLAlchemy()


class Pessoa:
    def descricao(self):
        return f"Pessoa: {getattr(self, 'nome', 'Sem nome')}"

    def tipo_pessoa(self):
        return "Pessoa"


class Funcionario(Pessoa, db.Model):
    __tablename__ = "funcionarios"

    id = db.Column(db.Integer, primary_key=True)
    cpf = db.Column(db.String(14), unique=True, nullable=False)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    telefone = db.Column(db.String(30), nullable=False)
    cep = db.Column(db.String(9))
    endereco = db.Column(db.String(255), nullable=False)
    data_nascimento = db.Column(db.Date)
    cargo = db.Column(db.String(80), nullable=False)
    salario = db.Column(db.Numeric(10, 2), default=0)
    horario_trabalho = db.Column(db.String(100))
    foto = db.Column(db.String(255))
    senha_hash = db.Column(db.String(255), nullable=False)
    perfil = db.Column(db.String(20), default="funcionario", nullable=False)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    tentativas_login = db.Column(db.Integer, default=0, nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    vendas = db.relationship("Venda", back_populates="funcionario")

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

    def descricao(self):
        return f"Funcionário: {self.nome} - {self.cargo}"

    def tipo_pessoa(self):
        return "Funcionário"

    @property
    def is_admin(self):
        return self.perfil == "admin"


class Categoria(db.Model):
    __tablename__ = "categorias"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)

    produtos = db.relationship("Produto", back_populates="categoria")


class Fornecedor(db.Model):
    __tablename__ = "fornecedores"

    id = db.Column(db.Integer, primary_key=True)
    nome_empresa = db.Column(db.String(140), nullable=False)
    representante = db.Column(db.String(120), nullable=False)
    telefone = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(120))
    cep = db.Column(db.String(9))
    endereco = db.Column(db.String(255))

    produtos = db.relationship("Produto", back_populates="fornecedor")


class Produto(db.Model):
    __tablename__ = "produtos"

    id = db.Column(db.Integer, primary_key=True)
    codigo_barras = db.Column(db.String(50), unique=True, nullable=False)
    nome = db.Column(db.String(140), nullable=False)
    valor_venda = db.Column(db.Numeric(10, 2), nullable=False)
    valor_custo = db.Column(db.Numeric(10, 2), nullable=False)
    descricao = db.Column(db.Text)
    estoque = db.Column(db.Integer, default=0, nullable=False)
    quantidade_minima = db.Column(db.Integer, default=0, nullable=False)
    foto = db.Column(db.String(255))
    categoria_id = db.Column(db.Integer, db.ForeignKey("categorias.id"), nullable=False)
    fornecedor_id = db.Column(db.Integer, db.ForeignKey("fornecedores.id"), nullable=False)

    categoria = db.relationship("Categoria", back_populates="produtos")
    fornecedor = db.relationship("Fornecedor", back_populates="produtos")
    itens_venda = db.relationship("VendaItem", back_populates="produto")
    alertas = db.relationship(
        "AlertaEstoque",
        back_populates="produto",
        cascade="all, delete-orphan",
    )

    @property
    def estoque_baixo(self):
        return self.estoque <= self.quantidade_minima


class Cliente(Pessoa, db.Model):
    __tablename__ = "clientes"

    id = db.Column(db.Integer, primary_key=True)
    cpf = db.Column(db.String(14), unique=True, nullable=False)
    nome = db.Column(db.String(120), nullable=False)
    telefone = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(120))
    data_nascimento = db.Column(db.Date)
    cep = db.Column(db.String(9))
    endereco = db.Column(db.String(255))
    itens_fidelidade = db.Column(db.Integer, default=0, nullable=False)

    vendas = db.relationship("Venda", back_populates="cliente")
    cupons = db.relationship(
        "Cupom",
        back_populates="cliente",
        cascade="all, delete-orphan",
    )

    def descricao(self):
        return f"Cliente: {self.nome} - {self.cpf}"

    def tipo_pessoa(self):
        return "Cliente"


class Cupom(db.Model):
    __tablename__ = "cupons"

    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(30), unique=True, nullable=False)
    desconto = db.Column(db.Integer, nullable=False)
    utilizado = db.Column(db.Boolean, default=False, nullable=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    usado_em = db.Column(db.DateTime)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False)

    cliente = db.relationship("Cliente", back_populates="cupons")
    vendas = db.relationship("Venda", back_populates="cupom")

    @property
    def ativo(self):
        return not self.utilizado


class Venda(db.Model):
    __tablename__ = "vendas"

    id = db.Column(db.Integer, primary_key=True)
    data_venda = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    desconto = db.Column(db.Numeric(10, 2), default=0, nullable=False)
    valor_total = db.Column(db.Numeric(10, 2), nullable=False)
    cliente_id = db.Column(db.Integer, db.ForeignKey("clientes.id"), nullable=False)
    funcionario_id = db.Column(db.Integer, db.ForeignKey("funcionarios.id"), nullable=False)
    cupom_id = db.Column(db.Integer, db.ForeignKey("cupons.id"))

    cliente = db.relationship("Cliente", back_populates="vendas")
    funcionario = db.relationship("Funcionario", back_populates="vendas")
    cupom = db.relationship("Cupom", back_populates="vendas")
    itens = db.relationship(
        "VendaItem",
        back_populates="venda",
        cascade="all, delete-orphan",
    )


class VendaItem(db.Model):
    __tablename__ = "venda_itens"

    id = db.Column(db.Integer, primary_key=True)
    quantidade = db.Column(db.Integer, nullable=False)
    valor_unitario = db.Column(db.Numeric(10, 2), nullable=False)
    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    venda_id = db.Column(db.Integer, db.ForeignKey("vendas.id"), nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey("produtos.id"), nullable=False)

    venda = db.relationship("Venda", back_populates="itens")
    produto = db.relationship("Produto", back_populates="itens_venda")


class AlertaEstoque(db.Model):
    __tablename__ = "alertas_estoque"

    id = db.Column(db.Integer, primary_key=True)
    data_ocorrencia = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    resolvido = db.Column(db.Boolean, default=False, nullable=False)
    produto_id = db.Column(db.Integer, db.ForeignKey("produtos.id"), nullable=False)

    produto = db.relationship("Produto", back_populates="alertas")
