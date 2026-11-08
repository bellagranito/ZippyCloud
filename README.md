# Zippy Cloud

Sistema web de gerenciamento de loja, feito em Python com Flask para a disciplina de Programação Orientada a Objetos. O banco de dados é SQLite e é acessado pelo SQLAlchemy.

## O que o sistema faz

- Login de funcionário por CPF ou e-mail e senha
- Usuário é inativado depois de 3 tentativas de senha erradas
- Cadastro de funcionários, clientes, fornecedores, categorias e produtos
- Carrinho e venda, com baixa automática no estoque
- Alerta quando o estoque fica no mínimo ou abaixo
- Cupom de fidelidade: a cada 10 itens comprados o cliente ganha 5% de desconto, até 45%
- Relatórios de faturamento, produtos mais vendidos, clientes, fornecedores e funcionários
- Busca de endereço pelo CEP (ViaCEP, precisa de internet)
- Tema claro e escuro

## Como executar

1. Ter o Python 3.11 ou mais novo instalado.
2. Abrir a pasta do projeto no VS Code.
3. Dar dois cliques em `INSTALAR_ZIPPY.bat`. Ele cria o ambiente virtual, instala as bibliotecas e cria o banco com os dados iniciais.
4. Depois, executar o `INICIAR_ZIPPY.bat`.
5. Abrir no navegador: http://127.0.0.1:5000

Se preferir fazer pelo terminal:

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python seed.py
python app.py
```

## Login inicial

O `seed.py` cria um administrador:

- E-mail: admin@zippycloud.com (ou CPF 000.000.000-00)
- Senha: Zippy@123

## Organização dos arquivos

- `app.py`: rotas e telas
- `models.py`: classes e tabelas do banco
- `services.py`: regras de negócio
- `config.py`: configurações
- `seed.py`: dados iniciais
- `templates/`: páginas HTML
- `static/`: CSS, JavaScript e imagens
- `documentacao/`: diagrama de classes

## Conceitos de POO

- Herança: `Funcionario` e `Cliente` herdam de `Pessoa`
- Polimorfismo: os dois sobrescrevem o método `descricao()`, que é chamado na tela de detalhes da venda (cliente e atendente aparecem com textos diferentes)
- Sobrecarga: `ProdutoService.buscar()` usa `singledispatchmethod` e funciona com `int` (busca por id) ou `str` (busca por nome ou código)
- Regras de negócio nas classes `AuthService`, `VendaService`, `EstoqueService` e `CupomService`
- Exceções: `ValidacaoError`, `RegraNegocioError` e `PersistenciaError`, com telas de erro 403, 404 e 500

## Observações

- A documentação pedia login por e-mail em um ponto e por CPF em outro, então o sistema aceita os dois.
- Também havia duas regras de senha diferentes, então foi usada a mais forte: 8 caracteres, uma letra maiúscula, um número e um caractere especial.
- Para usar PostgreSQL no lugar do SQLite, instalar o `requirements-cloud.txt` e definir a variável `DATABASE_URL`.
