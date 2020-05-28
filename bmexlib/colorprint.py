from colorama import Fore, Style


class ColorPrint:
    """
    Colorized Output Class
    """

    def red(self, data):
        print(Fore.RED + Style.BRIGHT + '[!] ' + Style.RESET_ALL + str(data))

    def green(self, data):
        print(Fore.GREEN + Style.BRIGHT + '[+] ' + Style.RESET_ALL + str(data))

    def yellow(self, data):
        print(Fore.YELLOW + Style.BRIGHT + '[i] ' + Style.RESET_ALL + str(data))

    def blue(self, data):
        print(Fore.BLUE + Style.BRIGHT + '[+] ' + Style.RESET_ALL + str(data))

    def cyan(self, data):
        print(Fore.CYAN + Style.BRIGHT + '[*] ' + Style.RESET_ALL + str(data))