import re
import secrets
from datetime import datetime
from decimal import Decimal
from functools import singledispatchmethod

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from models import (
    AlertaEstoque,
    Cliente,
    Cupom,
    Fornecedor,
    Funcionario,
    Produto,
    Venda,
    VendaItem,
    db,
)


class RegraNegocioError(Exception):
    pass


class ValidacaoError(RegraNegocioError):
    pass


class PersistenciaError(Exception):
    pass


class PersistenciaService:
    @staticmethod
    def confirmar(mensagem="Não foi possível salvar os dados. Tente novamente."):
        try:
            db.session.commit()
        except IntegrityError as exc:
            db.session.rollback()
            raise PersistenciaError(
                "Não foi possível salvar: existe informação duplicada ou relacionada de forma inválida."
            ) from exc
        except SQLAlchemyError as exc:
            db.session.rollback()
            raise PersistenciaError(mensagem) from exc

    @staticmethod
    def cancelar():
        db.session.rollback()


class ValidacaoService:
    @staticmethod
    def obrigatorios(**campos):
        faltantes = [nome for nome, valor in campos.items() if valor is None or str(valor).strip() == ""]
        if faltantes:
            nomes = ", ".join(faltantes)
            raise ValidacaoError(f"Preencha os campos obrigatórios: {nomes}.")

    @staticmethod
    def cpf(cpf: str):
        numeros = re.sub(r"\D", "", cpf or "")
        if len(numeros) != 11 or len(set(numeros)) == 1:
            raise ValidacaoError("Informe um CPF válido com 11 dígitos.")
        return cpf.strip()

    @staticmethod
    def telefone(telefone: str):
        numeros = re.sub(r"\D", "", telefone or "")
        if len(numeros) not in (10, 11):
            raise ValidacaoError("Informe um telefone válido com DDD.")
        return telefone.strip()

    @staticmethod
    def cep(cep: str, obrigatorio=False):
        if not cep and not obrigatorio:
            return ""
        numeros = re.sub(r"\D", "", cep or "")
        if len(numeros) != 8:
            raise ValidacaoError("Informe um CEP válido com 8 dígitos.")
        return cep.strip()

    @staticmethod
    def email(email: str, obrigatorio=False):
        email = (email or "").strip().lower()
        if not email and not obrigatorio:
            return ""
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise ValidacaoError("Informe um e-mail válido.")
        return email

    @staticmethod
    def nao_negativo(valor, campo):
        if valor < 0:
            raise ValidacaoError(f"{campo} não pode ser negativo.")
        return valor

    @staticmethod
    def inteiro_positivo(valor, campo="Quantidade"):
        if valor is None or int(valor) <= 0:
            raise ValidacaoError(f"{campo} deve ser maior que zero.")
        return int(valor)


class ProdutoService:
    @singledispatchmethod
    def buscar(self, valor):
        raise ValidacaoError("Tipo de busca de produto não suportado.")

    @buscar.register
    def _(self, valor: int):
        return db.session.get(Produto, valor)

    @buscar.register
    def _(self, valor: str):
        termo = valor.strip()
        if not termo:
            return Produto.query.order_by(Produto.nome).all()
        return Produto.query.filter(
            (Produto.nome.ilike(f"%{termo}%"))
            | (Produto.codigo_barras.ilike(f"%{termo}%"))
        ).order_by(Produto.nome).all()


class AuthService:
    @staticmethod
    def senha_forte(senha: str) -> bool:
        if len(senha) < 8:
            return False
        return bool(
            re.search(r"[A-Z]", senha)
            and re.search(r"\d", senha)
            and re.search(r"[^A-Za-z0-9]", senha)
        )

    @staticmethod
    def autenticar(identificador: str, senha: str):
        identificador = (identificador or "").strip()
        if not identificador or not senha:
            return None, "Informe CPF/e-mail e senha."

        funcionario = Funcionario.query.filter(
            (Funcionario.email == identificador) | (Funcionario.cpf == identificador)
        ).first()

        if not funcionario:
            return None, "CPF/e-mail ou senha inválidos."
        if not funcionario.ativo:
            return None, "Usuário inativo. Procure um administrador."

        if funcionario.verificar_senha(senha):
            funcionario.tentativas_login = 0
            PersistenciaService.confirmar("Não foi possível atualizar os dados de acesso.")
            return funcionario, None

        funcionario.tentativas_login += 1
        if funcionario.tentativas_login >= 3:
            funcionario.ativo = False
            PersistenciaService.confirmar("Não foi possível atualizar o bloqueio do usuário.")
            return None, "Usuário inativado após 3 tentativas incorretas."

        PersistenciaService.confirmar("Não foi possível atualizar as tentativas de login.")
        return None, f"Senha incorreta. Tentativa {funcionario.tentativas_login}/3."


class EstoqueService:
    @staticmethod
    def verificar_alerta(produto: Produto):
        if produto is None:
            raise RegraNegocioError("Produto não encontrado para verificar o estoque.")

        if produto.estoque <= produto.quantidade_minima:
            alerta = AlertaEstoque.query.filter_by(
                produto_id=produto.id,
                resolvido=False,
            ).first()
            if alerta:
                alerta.quantidade = produto.estoque
                alerta.data_ocorrencia = datetime.utcnow()
            else:
                db.session.add(
                    AlertaEstoque(
                        produto_id=produto.id,
                        quantidade=produto.estoque,
                    )
                )
        else:
            for alerta in AlertaEstoque.query.filter_by(
                produto_id=produto.id,
                resolvido=False,
            ).all():
                alerta.resolvido = True


class CupomService:
    @staticmethod
    def cupom_ativo(cliente: Cliente):
        if cliente is None:
            return None
        return Cupom.query.filter_by(
            cliente_id=cliente.id,
            utilizado=False,
        ).order_by(Cupom.id.desc()).first()

    @staticmethod
    def registrar_itens(cliente: Cliente, quantidade: int):
        if cliente is None:
            raise RegraNegocioError("Cliente é obrigatório para atualizar a fidelidade.")
        if quantidade <= 0:
            raise RegraNegocioError("A quantidade de itens da venda deve ser maior que zero.")

        cliente.itens_fidelidade += quantidade
        cupom = CupomService.cupom_ativo(cliente)

        while cliente.itens_fidelidade >= 10:
            cliente.itens_fidelidade -= 10
            if cupom:
                cupom.desconto = min(cupom.desconto + 5, 45)
            else:
                codigo = f"ZIP-{secrets.token_hex(3).upper()}"
                cupom = Cupom(
                    codigo=codigo,
                    desconto=5,
                    cliente_id=cliente.id,
                )
                db.session.add(cupom)
        return cupom

    @staticmethod
    def utilizar(cupom: Cupom, cliente: Cliente):
        if cupom is None:
            return
        if cupom.utilizado:
            raise RegraNegocioError("Este cupom já foi utilizado.")
        if cupom.cliente_id != cliente.id:
            raise RegraNegocioError("Este cupom não pertence ao cliente selecionado.")

        cupom.utilizado = True
        cupom.usado_em = datetime.utcnow()
        cliente.itens_fidelidade = 0


class VendaService:
    @staticmethod
    def calcular_total(carrinho):
        subtotal = Decimal("0.00")
        for item in carrinho:
            subtotal += Decimal(str(item["produto"].valor_venda)) * int(item["quantidade"])
        return subtotal

    @staticmethod
    def validar(cliente: Cliente, funcionario: Funcionario, carrinho, cupom: Cupom | None = None):
        if cliente is None:
            raise RegraNegocioError("Selecione um cliente antes de finalizar a venda.")
        if funcionario is None or not funcionario.ativo:
            raise RegraNegocioError("Funcionário inválido ou inativo para realizar a venda.")
        if not carrinho:
            raise RegraNegocioError("O carrinho está vazio.")

        for item in carrinho:
            produto = item.get("produto")
            quantidade = item.get("quantidade")
            if produto is None:
                raise RegraNegocioError("Há um produto inválido no carrinho.")
            try:
                quantidade = int(quantidade)
            except (TypeError, ValueError) as exc:
                raise RegraNegocioError(
                    f"Quantidade inválida para {produto.nome}."
                ) from exc
            if quantidade <= 0:
                raise RegraNegocioError(
                    f"A quantidade de {produto.nome} deve ser maior que zero."
                )
            if quantidade > produto.estoque:
                raise RegraNegocioError(
                    f"Estoque insuficiente para {produto.nome}. Disponível: {produto.estoque}."
                )

        if cupom:
            if cupom.utilizado:
                raise RegraNegocioError("O cupom selecionado já foi utilizado.")
            if cupom.cliente_id != cliente.id:
                raise RegraNegocioError("O cupom selecionado não pertence a este cliente.")

    @staticmethod
    def finalizar(cliente: Cliente, funcionario: Funcionario, carrinho, cupom: Cupom | None = None):
        VendaService.validar(cliente, funcionario, carrinho, cupom)

        try:
            subtotal = VendaService.calcular_total(carrinho)
            percentual = Decimal(str(cupom.desconto if cupom else 0))
            desconto = (subtotal * percentual / Decimal("100")).quantize(Decimal("0.01"))
            total = subtotal - desconto

            venda = Venda(
                cliente_id=cliente.id,
                funcionario_id=funcionario.id,
                cupom_id=cupom.id if cupom else None,
                subtotal=subtotal,
                desconto=desconto,
                valor_total=total,
            )
            db.session.add(venda)
            db.session.flush()

            quantidade_total = 0
            for item in carrinho:
                produto = item["produto"]
                qtd = int(item["quantidade"])
                quantidade_total += qtd
                produto.estoque -= qtd

                db.session.add(
                    VendaItem(
                        venda_id=venda.id,
                        produto_id=produto.id,
                        quantidade=qtd,
                        valor_unitario=produto.valor_venda,
                        subtotal=Decimal(str(produto.valor_venda)) * qtd,
                    )
                )
                EstoqueService.verificar_alerta(produto)

            if cupom:
                CupomService.utilizar(cupom, cliente)
            CupomService.registrar_itens(cliente, quantidade_total)

            PersistenciaService.confirmar("Não foi possível finalizar a venda. Tente novamente.")
            return venda
        except (RegraNegocioError, PersistenciaError):
            PersistenciaService.cancelar()
            raise
        except SQLAlchemyError as exc:
            PersistenciaService.cancelar()
            raise PersistenciaError(
                "Não foi possível finalizar a venda. Tente novamente."
            ) from exc


class ReportService:
    @staticmethod
    def indicadores():
        faturamento = db.session.query(
            func.coalesce(func.sum(Venda.valor_total), 0)
        ).scalar()
        vendas = Venda.query.count()
        produtos_baixos = Produto.query.filter(
            Produto.estoque <= Produto.quantidade_minima
        ).count()
        clientes = Cliente.query.count()
        return {
            "faturamento": faturamento,
            "vendas": vendas,
            "produtos_baixos": produtos_baixos,
            "clientes": clientes,
        }

    @staticmethod
    def produtos_mais_vendidos(limite=10):
        return db.session.query(
            Produto.nome,
            func.coalesce(func.sum(VendaItem.quantidade), 0).label("quantidade"),
        ).outerjoin(VendaItem).group_by(Produto.id).order_by(
            func.sum(VendaItem.quantidade).desc()
        ).limit(limite).all()

    @staticmethod
    def clientes_que_mais_compram(limite=10):
        return db.session.query(
            Cliente.nome,
            func.coalesce(func.sum(Venda.valor_total), 0).label("total"),
        ).outerjoin(Venda).group_by(Cliente.id).order_by(
            func.sum(Venda.valor_total).desc()
        ).limit(limite).all()

    @staticmethod
    def fornecedores_com_mais_produtos(limite=10):
        return db.session.query(
            Fornecedor.nome_empresa,
            func.count(Produto.id).label("quantidade"),
        ).outerjoin(Produto).group_by(Fornecedor.id).order_by(
            func.count(Produto.id).desc()
        ).limit(limite).all()

    @staticmethod
    def desempenho_funcionarios(limite=10):
        return db.session.query(
            Funcionario.nome,
            func.count(Venda.id).label("vendas"),
            func.coalesce(func.sum(Venda.valor_total), 0).label("total"),
        ).outerjoin(Venda).group_by(Funcionario.id).order_by(
            func.sum(Venda.valor_total).desc()
        ).limit(limite).all()
