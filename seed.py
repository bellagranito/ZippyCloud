from datetime import date
from app import app
from models import db, Funcionario, Categoria, Fornecedor, Produto, Cliente

with app.app_context():
    db.create_all()
    if not Funcionario.query.filter_by(email="admin@zippycloud.com").first():
        admin = Funcionario(
            cpf="000.000.000-00",
            nome="Administrador Zippy",
            email="admin@zippycloud.com",
            telefone="(18) 99999-0000",
            cep="16200-000",
            endereco="Birigui - SP",
            data_nascimento=date(2000, 1, 1),
            cargo="Administrador",
            salario=3000,
            horario_trabalho="08:00 às 18:00",
            perfil="admin",
        )
        admin.set_senha("Zippy@123")
        db.session.add(admin)

    if not Categoria.query.first():
        brinquedos = Categoria(nome="Brinquedos")
        eletronicos = Categoria(nome="Eletrônicos")
        papelaria = Categoria(nome="Papelaria")
        db.session.add_all([brinquedos, eletronicos, papelaria])
        db.session.flush()

        fornecedor = Fornecedor(
            nome_empresa="Mundo Distribuidora",
            representante="Carlos Souza",
            telefone="(18) 99888-1122",
            email="contato@mundodistribuidora.com",
            cep="16010-000",
            endereco="Araçatuba - SP",
        )
        db.session.add(fornecedor)
        db.session.flush()

        db.session.add_all([
            Produto(codigo_barras="789100001", nome="Carrinho Speed", valor_venda=39.90, valor_custo=22.00, descricao="Carrinho de brinquedo", estoque=18, quantidade_minima=5, categoria_id=brinquedos.id, fornecedor_id=fornecedor.id),
            Produto(codigo_barras="789100002", nome="Boneca Estrela", valor_venda=89.90, valor_custo=55.00, descricao="Boneca articulada", estoque=4, quantidade_minima=5, categoria_id=brinquedos.id, fornecedor_id=fornecedor.id),
            Produto(codigo_barras="789100003", nome="Fone Bluetooth", valor_venda=119.90, valor_custo=74.00, descricao="Fone sem fio", estoque=11, quantidade_minima=3, categoria_id=eletronicos.id, fornecedor_id=fornecedor.id),
        ])

        cliente = Cliente(cpf="111.222.333-44", nome="Ana Martins", telefone="(18) 99777-3322", email="ana@email.com", data_nascimento=date(1998, 5, 10), cep="16200-000", endereco="Birigui - SP")
        db.session.add(cliente)

    db.session.commit()
    print("Banco inicializado.")
    print("Login: admin@zippycloud.com ou 000.000.000-00")
    print("Senha: Zippy@123")
