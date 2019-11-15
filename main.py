from menus import menu_thiessen, menu_download

print("######################################")
print("#   Bem vindo ao PyHidroweb v. 0.0.6 #")
print("######################################")
print("\n")

while True:
    print("Escolha uma opção:")
    print("1 - Download")
    print("2 - Thiessen")
    print("3 - Sair")
    option = input()
    if option == '1':
        menu_download()
    elif option == '2':
        menu_thiessen()
    elif option == '3':
        break
    else:
        print("Opção inválida")
    
    print('\n')

print("Programa encerrado")
