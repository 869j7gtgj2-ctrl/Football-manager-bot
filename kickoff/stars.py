"""Approximate ability ratings (game scale 1-99) for well-known players.

Everyone else in a real squad gets an estimate from the club's level, age and squad number.
Names are matched accent- and case-insensitively, by full name or by "initial + surname".
"""
from __future__ import annotations

import unicodedata

STARS = {
    # world class
    "Kylian Mbappé": 92, "Erling Haaland": 92, "Mohamed Salah": 89, "Jude Bellingham": 90, "Vinícius Júnior": 90,
    "Lamine Yamal": 91, "Rodri": 89, "Harry Kane": 90, "Kevin De Bruyne": 85, "Virgil van Dijk": 88,
    "Raphinha": 88, "Pedri": 89, "Florian Wirtz": 88, "Jamal Musiala": 89, "Bukayo Saka": 88, "Declan Rice": 87,
    "Martin Ødegaard": 87, "William Saliba": 88, "Alisson": 88, "Thibaut Courtois": 89, "Gianluigi Donnarumma": 88,
    "Ousmane Dembélé": 90, "Achraf Hakimi": 88, "Vitinha": 89, "Lautaro Martínez": 88, "Nicolò Barella": 87,
    "Alessandro Bastoni": 87, "Federico Valverde": 88, "Aurélien Tchouaméni": 86, "Joshua Kimmich": 87,
    "Alexander Isak": 88, "Cole Palmer": 88, "Moisés Caicedo": 87, "Enzo Fernández": 85, "Phil Foden": 86,
    "Bruno Fernandes": 86, "Alexis Mac Allister": 86, "Ryan Gravenberch": 86, "Dominik Szoboszlai": 86,
    "Khvicha Kvaratskhelia": 88, "Désiré Doué": 86, "João Neves": 87, "Nuno Mendes": 87, "Marquinhos": 86,
    "Antoine Griezmann": 84, "Jan Oblak": 87, "Julián Álvarez": 87, "Robert Lewandowski": 85, "Frenkie de Jong": 86,
    "Jules Koundé": 86, "Ronald Araújo": 84, "Pau Cubarsí": 86, "Marc-André ter Stegen": 85, "Joan García": 85,
    "Dani Olmo": 85, "Fermín López": 84, "Gavi": 84, "Eduardo Camavinga": 85, "Rodrygo": 85, "Arda Güler": 85,
    "Dean Huijsen": 84, "Trent Alexander-Arnold": 86, "Antonio Rüdiger": 85, "Éder Militão": 84, "Franco Mastantuono": 80,
    "Michael Olise": 88, "Leroy Sané": 84, "Dayot Upamecano": 85, "Manuel Neuer": 85, "Luis Díaz": 87,
    "Serhou Guirassy": 85, "Gregor Kobel": 86, "Karim Adeyemi": 82, "Nico Schlotterbeck": 85, "Julian Brandt": 83,
    "Granit Xhaka": 84, "Victor Boniface": 82, "Patrik Schick": 82, "Xavi Simons": 85, "Benjamin Šeško": 84,
    "Hugo Ekitiké": 85, "Omar Marmoush": 85, "Deniz Undav": 82, "Angelo Stiller": 83,
    "Hakan Çalhanoğlu": 85, "Marcus Thuram": 85, "Yann Sommer": 84, "Federico Dimarco": 85, "Denzel Dumfries": 84,
    "Scott McTominay": 86, "Kevin De Bruyne ": 85, "Romelu Lukaku": 83, "Stanislav Lobotka": 85, "Alex Meret": 82,
    "Rasmus Højlund": 83, "Dušan Vlahović": 84, "Kenan Yıldız": 85, "Gleison Bremer": 85, "Teun Koopmeiners": 83,
    "Rafael Leão": 86, "Christian Pulisic": 85, "Mike Maignan": 87, "Luka Modrić": 84, "Ademola Lookman": 85,
    "Mateo Retegui": 83, "Paulo Dybala": 82, "Artem Dovbyk": 82, "Mile Svilar": 84, "Nico Paz": 83,
    "Mattia Zaccagni": 82, "Riccardo Orsolini": 82, "Moise Kean": 84,
    "Mason Greenwood": 84, "Pierre-Emerick Aubameyang": 80, "Jonathan David": 84, "Lucas Chevalier": 85,
    "Rayan Cherki": 85, "Bradley Barcola": 86, "Gonçalo Ramos": 83, "Fabián Ruiz": 85, "Willian Pacho": 85,
    "Takumi Minamino": 81, "Lucas Hernandez": 83,
    "Bruno Guimarães": 86, "Sandro Tonali": 85, "Anthony Gordon": 84, "Nick Woltemade": 83, "Ollie Watkins": 84,
    "Morgan Rogers": 84, "Emiliano Martínez": 86, "Youri Tielemans": 83, "John McGinn": 82, "Son Heung-min": 84,
    "James Maddison": 83, "Mohammed Kudus": 84, "Micky van de Ven": 84, "Cristian Romero": 85, "Guglielmo Vicario": 84,
    "Kaoru Mitoma": 83, "Morgan Gibbs-White": 83, "Murillo": 83, "Chris Wood": 82, "Eberechi Eze": 85,
    "Jean-Philippe Mateta": 82, "Marc Guéhi": 85, "Dean Henderson": 82, "Antoine Semenyo": 84, "Bryan Mbeumo": 85,
    "Matheus Cunha": 85, "Benjamin Šeško ": 84, "Amad Diallo": 82, "Lisandro Martínez": 83, "Kobbie Mainoo": 82,
    "Viktor Gyökeres": 86, "Eberechi Eze ": 85, "Gabriel Magalhães": 87, "David Raya": 87, "Jurriën Timber": 85,
    "Riccardo Calafiori": 83, "Martín Zubimendi": 86, "Noni Madueke": 82, "Gabriel Martinelli": 83,
    "Leandro Trossard": 82, "Kai Havertz": 84, "Mikel Merino": 84, "Ibrahima Konaté": 86, "Cody Gakpo": 85,
    "Federico Chiesa": 79, "Jeremie Frimpong": 84, "Milos Kerkez": 84, "Josko Gvardiol": 86, "Joško Gvardiol": 86,
    "Rúben Dias": 87, "Bernardo Silva": 85, "Tijjani Reijnders": 85, "Jérémy Doku": 83, "Savinho": 82,
    "Nico O'Reilly": 80, "Rayan Aït-Nouri": 83, "Gianluigi Donnarumma ": 88, "Robert Sánchez": 82,
    "Marc Cucurella": 85, "Reece James": 85, "Levi Colwill": 84, "João Pedro": 85, "Pedro Neto": 84,
    "Liam Delap": 81, "Estêvão": 83, "Jamie Gittens": 81, "Jarrod Bowen": 83,
    "Iñaki Williams": 82, "Nico Williams": 86, "Oihan Sancet": 82, "Unai Simón": 85, "Mikel Oyarzabal": 84,
    "Takefusa Kubo": 82, "Álex Baena": 84, "Giorgi Mamardashvili": 84, "Isco": 82, "Antony": 81,
    "Iago Aspas": 79, "Ayoze Pérez": 82, "Gerard Moreno": 81, "Koke": 81, "Pablo Barrios": 83,
    "Alexander Sørloth": 83, "Giuliano Simeone": 82, "José María Giménez": 82,
    # Ukrainians and UPL
    "Mykhailo Mudryk": 79, "Oleksandr Zinchenko": 80, "Illia Zabarnyi": 84, "Anatoliy Trubin": 84,
    "Georgiy Sudakov": 83, "Heorhiy Sudakov": 83, "Viktor Tsyhankov": 81, "Mykola Matviyenko": 81, "Mykola Matviienko": 81,
    "Vitaliy Mykolenko": 82, "Artem Dovbyk ": 82, "Roman Yaremchuk": 78, "Oleksandr Svatok": 77,
    "Vladyslav Vanat": 79, "Dmytro Riznyk": 77, "Valeriy Bondar": 77, "Yukhym Konoplya": 76, "Oleh Ocheretko": 76,
    "Artem Bondarenko": 77, "Pedrinho": 77, "Kevin": 78, "Eguinaldo": 77, "Marlon Gomes": 76, "Lassina Traoré": 76,
    "Danylo Sikan": 75, "Oleksandr Zubkov": 77, "Heorhiy Bushchan": 76, "Vitaliy Buyalskyi": 75,
    "Mykola Shaparenko": 77, "Volodymyr Brazhko": 77, "Oleksandr Pikhalonok": 76, "Nazar Voloshyn": 76,
    "Oleksandr Tymchyk": 74, "Maksym Talovierov": 74, "Ruslan Malinovskyi": 80, "Ivan Kalyuzhnyi": 76,
    "Bohdan Mykhaylichenko": 74, "Andriy Yarmolenko": 72,
}


def norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return " ".join(s.replace("-", " ").replace(".", " ").split())


def _index(stars: dict) -> dict:
    idx = {}
    for name, r in stars.items():
        n = norm(name)
        idx[n] = r
        parts = n.split()
        if len(parts) >= 2:
            idx.setdefault(f"{parts[0][0]} {parts[-1]}", r)
    return idx


_DEFAULT_INDEX = _index(STARS)


def lookup(name: str, stars: dict | None = None) -> int | None:
    idx = _DEFAULT_INDEX if not stars else _index({**STARS, **stars})
    n = norm(name)
    if n in idx:
        return idx[n]
    parts = n.split()
    if len(parts) >= 2:
        return idx.get(f"{parts[0][0]} {parts[-1]}")
    return None
