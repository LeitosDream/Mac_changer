#!/bin/python
import random
import subprocess
import re
import sys
import requests
import string
from argparse import ArgumentParser
from bs4 import BeautifulSoup


class MacChanger:
    def __init__(self):
        """Конструктор класса"""
        self.regex_mac = re.compile(r'(?:[0-9a-fA-F]:?){12}')  # Регулярка для поиска mac
        self.regex_iface = re.compile(r"\w+:\s")  # Регулярка для поиска интерфейса в выводе ifconfig
        self.mac_slice = "abcdfABCDF" + string.digits  # Строка для формаирования mac
        self.check_arguments()

    def check_arguments(self):
        """Это меню аргументов Выполняется первым при запуске"""
        parser = ArgumentParser(description="Mac Changer")
        parser.add_argument("method", help="show, change")
        parser.add_argument("-t", "--type", help="vendor, random, rand_vendor, const, my", default=None)
        parser.add_argument("-i", "--iface", default=None)
        parser.add_argument("-m", "--mac", default=None)
        args = parser.parse_args()
        if args.method.lower() == "show":
            self.check_current_mac("show")
        elif args.method.lower() == "change":
            # Проверяем провильно ли введён тип работы
            if args.type in ("vendor", "random", "const", "my", "rand_vendor"):
                # Проверяем есть ли введённый интерфейс на самом деле
                try:
                    self.check_current_mac("generate")[args.iface]
                except KeyError:
                    print("Enter correct interface name")
                    return
                if args.type.lower() == "vendor":
                    self.generate_random_mac("vendor", args.iface)
                elif args.type.lower() == "random":
                    self.generate_random_mac("random", args.iface)
                elif args.type.lower() == "const":
                    self.back_to_original_mac(args.iface)
                elif args.type.lower() == "my":
                    # Проверяем формат введённого mac
                    if re.findall(self.regex_mac, args.mac):
                        self.changing_mac(args.iface, args.mac)
                    else:
                        print("Enter correct mac with format 00:00:00:00:00:00")
                        return
                elif args.type.lower() == "rand_vendor":
                    self.changing_random_vendor("generate_mac", args.iface)
            else:
                print("Enter correct work type")
                return

    def check_current_mac(self, method):
        """Функция проверки и вывода текущих маков"""
        shell_out = subprocess.run("ifconfig", stdout=subprocess.PIPE)
        mac_dict = {}
        for iface in re.findall(self.regex_iface, str(shell_out.stdout).replace('\\n', ' ')):
            shell_const_mac = subprocess.run(["ethtool", "-P", f"{iface[:-2]}"], stdout=subprocess.PIPE)
            shell_out_mac = subprocess.run(["ifconfig", f"{iface[:-2]}"], stdout=subprocess.PIPE)
            # shell_out_mac = subprocess.run(["ifconfig", f"{iface[:-2]}", "|", "grep", "|", "ether", "|", "gawk", "'{print $2}'"], stdout=subprocess.PIPE)
            # ifconfig eth0 | grep ether | gawk '{print $2}'
            const_mac = re.findall(self.regex_mac, shell_const_mac.stdout.decode())
            real_mac = re.findall(r"ether (?:[0-9a-fA-F]:?){12}", shell_out_mac.stdout.decode())
            mac_dict[iface[:-2]] = (const_mac[0] if const_mac else "",
                                    real_mac[0].replace("ether ", "") if real_mac else "")
        if method == "show":
            print("\n\n  Interface".center(12), "Const mac".center(29), "Real mac".center(12), "Vendor".center(48))
            print("-" * 103)
            for iface, mac in mac_dict.items():
                vendors = self.changing_random_vendor("check_vendor")
                vendor_mac = mac[1][:9].replace(":", "").upper()
                vendor = ""
                if vendor_mac in vendors:
                    vendor = vendors[vendor_mac]
                print(
                    f"|  {iface.center(10)}  |  {mac[0].center(17)}  |  {mac[1].center(17)}  |  {vendor.center(38)}  |")
                print("-" * 103)
        elif method == "generate":
            return mac_dict

    def changing_mac(self, iface: str, mac: str):
        """Функция смены mac"""
        subprocess.call(["ifconfig", iface, "down"])
        subprocess.call(["ifconfig", iface, "hw", "ether", mac])
        subprocess.call(["ifconfig", iface, "up"])
        real_mac = subprocess.run(["ifconfig", f"{iface}"], stdout=subprocess.PIPE)
        mac = re.findall(r"ether (?:[0-9a-fA-F]:?){12}", real_mac.stdout.decode())
        print(f"mac in interface {iface} changed to {mac[0].replace('ether ', '')}")

    def changing_random_vendor(self, method: str, interface: str = None):
        """Функция проверки вендоров через сайт"""
        try:
            ans = requests.get("https://migera.ru/hard/manual/mac_table.html")
            soup = BeautifulSoup(ans.text, "lxml")
            vendors = {}
            for val in soup.find("td", {"id": "main_tbl"}).find_all("tr"):
                lst_vendors = str(val).split("</td><td>")
                vendors[lst_vendors[0].replace("<tr><td>", "")] = lst_vendors[1].replace("</td></tr>", "")
            if method == "generate_mac":
                vendor = random.choice(list(vendors.items()))
                index = 2
                vendor_mac = ":".join([vendor[0][i:i + index] for i in range(0, len(vendor[0]), index)])
                self.generate_random_mac("vendor_random", interface, vendor_mac)
            elif method == "check_vendor":
                return vendors
        except requests.exceptions.ConnectionError:  # Нужно для ситуации, когда сеть не доступна
            print("Сайт не доступен")
            sys.exit(0)

    def generate_random_mac(self, method: str, interface: str, mac: str = None):
        """Функция генерации случайных маков, работает в разных режимах"""
        iters = 5 if method == "random" else 3
        new_mac = ""
        if method == "vendor":
            new_mac = self.check_current_mac("generate")[interface][1][:8]
        elif method == "random":
            new_mac = "".join(random.choices(self.mac_slice, k=2))
        elif method == "vendor_random":
            new_mac = mac
        for i in range(iters):
            rand_bit = "".join(random.choices(self.mac_slice, k=2))
            new_mac += f":{rand_bit}"
        self.changing_mac(interface, new_mac)

    def back_to_original_mac(self, interface: str):
        """Функция возвращения к маку, заложенному производителем"""
        original_mac = self.check_current_mac("generate")[interface][0]
        self.changing_mac(interface, original_mac)


if __name__ == "__main__":
    MacChanger()
