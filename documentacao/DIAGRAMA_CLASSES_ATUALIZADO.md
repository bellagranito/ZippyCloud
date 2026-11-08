# Diagrama de classes

O diagrama está em `DIAGRAMA_CLASSES_ATUALIZADO.png` (também em `.svg`).

Mudanças em relação ao diagrama antigo:

- Foi criada a classe `Pessoa`, e `Funcionario` e `Cliente` herdam dela.
- Foram adicionadas as classes `VendaItem` e `AlertaEstoque`.
- O carrinho não é uma classe do banco, ele fica guardado na sessão do Flask.
- Os relatórios são feitos pela classe `ReportService`.
- As classes de serviço aparecem separadas porque ficam com as regras de negócio.
