"""Name pools for generated players (academy graduates, regens) and nationality helpers.

Real squads come from kickoff/realdata.py; these pools are only for invented players, picked by nationality.
"""
from __future__ import annotations

import random

POOLS = {
    "UA": (["Oleksandr", "Andriy", "Bohdan", "Vladyslav", "Vitaliy", "Dmytro", "Denys", "Yevhen", "Ivan", "Ihor",
            "Maksym", "Mykola", "Nazar", "Oleh", "Ostap", "Petro", "Roman", "Serhiy", "Taras", "Yuriy", "Yaroslav",
            "Artem", "Vadym", "Kyrylo", "Mykhailo", "Danylo", "Matviy", "Orest", "Sviatoslav", "Heorhiy"],
           ["Kovalenko", "Bondar", "Tkachuk", "Kravets", "Melnyk", "Shevchuk", "Boiko", "Polishchuk", "Lysenko",
            "Honchar", "Savchuk", "Rudenko", "Moroz", "Oliynyk", "Kuzmenko", "Pavliuk", "Demchuk", "Kozak", "Lytvyn",
            "Sydorenko", "Humeniuk", "Marchenko", "Khymych", "Borysiuk", "Yatsyshyn", "Holovatyi", "Zinchuk",
            "Ostapchuk", "Dorosh", "Verbytskyi", "Pylypchuk", "Stetsiuk", "Tereshchuk", "Hutsuliak", "Karpenko"]),
    "EN": (["Jack", "Harry", "Oliver", "George", "Charlie", "James", "Alfie", "Leo", "Freddie", "Archie", "Tom",
            "Ben", "Callum", "Ethan", "Kieran", "Mason", "Reece", "Tyler", "Josh", "Sam"],
           ["Smith", "Jones", "Taylor", "Brown", "Williams", "Wilson", "Johnson", "Davies", "Robinson", "Wright",
            "Thompson", "Walker", "White", "Hughes", "Edwards", "Green", "Hall", "Wood", "Clarke", "Turner"]),
    "ES": (["Javier", "Sergio", "Álvaro", "Diego", "Pablo", "Iker", "Hugo", "Marcos", "Adrián", "Raúl", "Unai",
            "Mikel", "Dani", "Rubén", "Carlos", "Gonzalo"],
           ["García", "Martínez", "López", "Sánchez", "Pérez", "Gómez", "Ruiz", "Navarro", "Moreno", "Ortega",
            "Romero", "Iglesias", "Castillo", "Herrera", "Molina", "Vidal"]),
    "DE": (["Lukas", "Leon", "Finn", "Jonas", "Niklas", "Felix", "Tim", "Julian", "Moritz", "Jannik", "Paul",
            "Maximilian", "Tobias", "Florian"],
           ["Müller", "Schmidt", "Schneider", "Fischer", "Weber", "Meyer", "Wagner", "Becker", "Hoffmann", "Koch",
            "Richter", "Klein", "Wolf", "Neumann", "Braun", "Krüger"]),
    "IT": (["Lorenzo", "Matteo", "Alessandro", "Andrea", "Federico", "Riccardo", "Davide", "Gabriele", "Tommaso",
            "Nicolò", "Simone", "Marco", "Filippo"],
           ["Rossi", "Russo", "Ferrari", "Esposito", "Bianchi", "Romano", "Colombo", "Ricci", "Marino", "Greco",
            "Bruno", "Gallo", "Conti", "De Luca", "Mancini", "Lombardi"]),
    "FR": (["Lucas", "Hugo", "Théo", "Mathis", "Enzo", "Nathan", "Louis", "Rayan", "Kylian", "Bastien", "Maxence",
            "Yanis", "Clément", "Antoine"],
           ["Martin", "Bernard", "Dubois", "Thomas", "Robert", "Richard", "Petit", "Durand", "Leroy", "Moreau",
            "Simon", "Laurent", "Lefebvre", "Michel", "Fofana", "Diallo", "Camara"]),
    "BR": (["Lucas", "Gabriel", "Matheus", "Vitor", "Thiago", "Caio", "Luan", "Renan", "Igor", "Vinícius",
            "Rodrygo", "Pedro", "Kaio", "Wesley"],
           ["Silva", "Santos", "Souza", "Oliveira", "Pereira", "Lima", "Costa", "Ribeiro", "Alves", "Gomes",
            "Martins", "Rocha", "Barbosa", "Moreira"]),
    "PT": (["João", "Rúben", "Diogo", "Gonçalo", "Tiago", "Rafael", "Francisco", "Nuno", "Bruno"],
           ["Silva", "Fernandes", "Carvalho", "Mendes", "Neves", "Costa", "Pinto", "Ramos", "Dias"]),
    "NL": (["Daan", "Sem", "Jesse", "Bram", "Thijs", "Lars", "Ruben", "Milan"],
           ["de Jong", "van Dijk", "Bakker", "Visser", "Smit", "de Vries", "Mulder", "Meijer"]),
    "AR": (["Facundo", "Nicolás", "Lautaro", "Thiago", "Valentín", "Matías", "Agustín", "Franco"],
           ["González", "Rodríguez", "Fernández", "Álvarez", "Romero", "Díaz", "Acosta", "Benítez"]),
    "PL": (["Kacper", "Jakub", "Maciej", "Szymon", "Filip", "Mateusz"],
           ["Nowak", "Wójcik", "Kowalczyk", "Zieliński", "Lewandowski", "Kamiński"]),
    "HR": (["Luka", "Ivan", "Mateo", "Duje", "Josip", "Marko"], ["Horvat", "Kovačić", "Babić", "Perić", "Jurić", "Matić"]),
    "AF": (["Ibrahim", "Moussa", "Amadou", "Sekou", "Emeka", "Kofi", "Yaw", "Ousmane"],
           ["Traoré", "Koné", "Diop", "Ndiaye", "Mensah", "Okafor", "Adeyemi", "Sarr"]),
}

# nation code -> (flag emoji, pool key)
NATIONS = {
    "UA": ("🇺🇦", "UA"), "EN": ("🏴󠁧󠁢󠁥󠁮󠁧󠁿", "EN"), "SC": ("🏴󠁧󠁢󠁳󠁣󠁴󠁿", "EN"), "WA": ("🏴󠁧󠁢󠁷󠁬󠁳󠁿", "EN"), "IE": ("🇮🇪", "EN"),
    "NIR": ("🇬🇧", "EN"), "ES": ("🇪🇸", "ES"), "DE": ("🇩🇪", "DE"), "AT": ("🇦🇹", "DE"), "CH": ("🇨🇭", "DE"),
    "IT": ("🇮🇹", "IT"), "FR": ("🇫🇷", "FR"), "BE": ("🇧🇪", "FR"), "BR": ("🇧🇷", "BR"), "PT": ("🇵🇹", "PT"),
    "NL": ("🇳🇱", "NL"), "AR": ("🇦🇷", "AR"), "UY": ("🇺🇾", "AR"), "CO": ("🇨🇴", "AR"), "MX": ("🇲🇽", "AR"),
    "PL": ("🇵🇱", "PL"), "CZ": ("🇨🇿", "PL"), "SK": ("🇸🇰", "PL"), "HR": ("🇭🇷", "HR"), "RS": ("🇷🇸", "HR"),
    "SI": ("🇸🇮", "HR"), "BA": ("🇧🇦", "HR"), "GE": ("🇬🇪", "UA"), "DK": ("🇩🇰", "NL"), "NO": ("🇳🇴", "NL"),
    "SE": ("🇸🇪", "NL"), "SN": ("🇸🇳", "AF"), "CI": ("🇨🇮", "AF"), "NG": ("🇳🇬", "AF"), "GH": ("🇬🇭", "AF"),
    "CM": ("🇨🇲", "AF"), "ML": ("🇲🇱", "AF"), "MA": ("🇲🇦", "FR"), "DZ": ("🇩🇿", "FR"), "EG": ("🇪🇬", "AF"),
    "US": ("🇺🇸", "EN"), "JP": ("🇯🇵", "EN"), "KR": ("🇰🇷", "EN"), "TR": ("🇹🇷", "DE"), "GR": ("🇬🇷", "IT"),
    "HU": ("🇭🇺", "PL"), "RO": ("🇷🇴", "IT"), "AL": ("🇦🇱", "IT"), "EC": ("🇪🇨", "AR"), "CL": ("🇨🇱", "AR"),
    "PY": ("🇵🇾", "AR"), "VE": ("🇻🇪", "AR"), "AU": ("🇦🇺", "EN"), "CA": ("🇨🇦", "EN"), "MD": ("🇲🇩", "UA"),
    "AM": ("🇦🇲", "UA"), "AZ": ("🇦🇿", "UA"), "LT": ("🇱🇹", "PL"), "LV": ("🇱🇻", "PL"), "EE": ("🇪🇪", "PL"),
    "FI": ("🇫🇮", "NL"), "IS": ("🇮🇸", "NL"), "BG": ("🇧🇬", "HR"), "MK": ("🇲🇰", "HR"), "ME": ("🇲🇪", "HR"),
    "XK": ("🇽🇰", "HR"), "GN": ("🇬🇳", "AF"), "CD": ("🇨🇩", "AF"), "GA": ("🇬🇦", "AF"), "TN": ("🇹🇳", "FR"),
    "BF": ("🇧🇫", "AF"), "GM": ("🇬🇲", "AF"), "ZA": ("🇿🇦", "AF"), "JM": ("🇯🇲", "EN"), "PE": ("🇵🇪", "AR"),
    "IL": ("🇮🇱", "EN"), "KZ": ("🇰🇿", "UA"), "UZ": ("🇺🇿", "UA"), "BY": ("🇧🇾", "UA"), "CV": ("🇨🇻", "PT"),
    "AO": ("🇦🇴", "PT"), "MZ": ("🇲🇿", "PT"),
}

# FIFA 3-letter codes (Wikipedia squads) -> nation code
FIFA = {
    "UKR": "UA", "ENG": "EN", "SCO": "SC", "WAL": "WA", "IRL": "IE", "NIR": "NIR", "ESP": "ES", "GER": "DE",
    "AUT": "AT", "SUI": "CH", "ITA": "IT", "FRA": "FR", "BEL": "BE", "BRA": "BR", "POR": "PT", "NED": "NL",
    "ARG": "AR", "URU": "UY", "COL": "CO", "MEX": "MX", "POL": "PL", "CZE": "CZ", "SVK": "SK", "CRO": "HR",
    "SRB": "RS", "SVN": "SI", "BIH": "BA", "GEO": "GE", "DEN": "DK", "NOR": "NO", "SWE": "SE", "SEN": "SN",
    "CIV": "CI", "NGA": "NG", "GHA": "GH", "CMR": "CM", "MLI": "ML", "MAR": "MA", "ALG": "DZ", "EGY": "EG",
    "USA": "US", "JPN": "JP", "KOR": "KR", "TUR": "TR", "GRE": "GR", "HUN": "HU", "ROU": "RO", "ALB": "AL",
    "ECU": "EC", "CHI": "CL", "PAR": "PY", "VEN": "VE", "AUS": "AU", "CAN": "CA", "MDA": "MD", "ARM": "AM",
    "AZE": "AZ", "LTU": "LT", "LVA": "LV", "EST": "EE", "FIN": "FI", "ISL": "IS", "BUL": "BG", "MKD": "MK",
    "MNE": "ME", "KVX": "XK", "GUI": "GN", "COD": "CD", "GAB": "GA", "TUN": "TN", "BFA": "BF", "GAM": "GM",
    "RSA": "ZA", "JAM": "JM", "PER": "PE", "ISR": "IL", "KAZ": "KZ", "UZB": "UZ", "BLR": "BY", "CPV": "CV",
    "ANG": "AO", "MOZ": "MZ",
}

# Country names (football-data.org) -> nation code
COUNTRY = {
    "Ukraine": "UA", "England": "EN", "Scotland": "SC", "Wales": "WA", "Republic of Ireland": "IE", "Ireland": "IE",
    "Northern Ireland": "NIR", "Spain": "ES", "Germany": "DE", "Austria": "AT", "Switzerland": "CH", "Italy": "IT",
    "France": "FR", "Belgium": "BE", "Brazil": "BR", "Portugal": "PT", "Netherlands": "NL", "Argentina": "AR",
    "Uruguay": "UY", "Colombia": "CO", "Mexico": "MX", "Poland": "PL", "Czech Republic": "CZ", "Czechia": "CZ",
    "Slovakia": "SK", "Croatia": "HR", "Serbia": "RS", "Slovenia": "SI", "Bosnia and Herzegovina": "BA",
    "Bosnia-Herzegovina": "BA", "Georgia": "GE", "Denmark": "DK", "Norway": "NO", "Sweden": "SE", "Senegal": "SN",
    "Ivory Coast": "CI", "Côte d'Ivoire": "CI", "Nigeria": "NG", "Ghana": "GH", "Cameroon": "CM", "Mali": "ML",
    "Morocco": "MA", "Algeria": "DZ", "Egypt": "EG", "United States": "US", "USA": "US", "Japan": "JP",
    "South Korea": "KR", "Korea Republic": "KR", "Turkey": "TR", "Türkiye": "TR", "Greece": "GR", "Hungary": "HU",
    "Romania": "RO", "Albania": "AL", "Ecuador": "EC", "Chile": "CL", "Paraguay": "PY", "Venezuela": "VE",
    "Australia": "AU", "Canada": "CA", "Moldova": "MD", "Armenia": "AM", "Azerbaijan": "AZ", "Lithuania": "LT",
    "Latvia": "LV", "Estonia": "EE", "Finland": "FI", "Iceland": "IS", "Bulgaria": "BG", "North Macedonia": "MK",
    "Montenegro": "ME", "Kosovo": "XK", "Guinea": "GN", "DR Congo": "CD", "Congo DR": "CD", "Gabon": "GA",
    "Tunisia": "TN", "Burkina Faso": "BF", "Gambia": "GM", "South Africa": "ZA", "Jamaica": "JM", "Peru": "PE",
    "Israel": "IL", "Kazakhstan": "KZ", "Uzbekistan": "UZ", "Belarus": "BY", "Cape Verde": "CV", "Angola": "AO",
    "Mozambique": "MZ",
}

# Typical foreign-player mix per league nation (weights for generated squads / regens)
LEAGUE_MIX = {
    "UA": [("UA", 85), ("BR", 8), ("GE", 2), ("AF", 3), ("HR", 2)],
    "EN": [("EN", 45), ("FR", 8), ("BR", 8), ("ES", 5), ("PT", 5), ("NL", 5), ("AF", 10), ("AR", 4), ("DE", 4), ("IE", 6)],
    "ES": [("ES", 65), ("FR", 6), ("BR", 6), ("AR", 8), ("PT", 3), ("AF", 6), ("NL", 3), ("UY", 3)],
    "DE": [("DE", 55), ("AT", 6), ("CH", 4), ("FR", 7), ("NL", 4), ("DK", 4), ("AF", 8), ("PL", 4), ("HR", 4), ("BR", 4)],
    "IT": [("IT", 55), ("FR", 6), ("BR", 5), ("AR", 7), ("ES", 4), ("NL", 4), ("AF", 7), ("HR", 4), ("PL", 4), ("DK", 4)],
    "FR": [("FR", 60), ("AF", 18), ("MA", 5), ("BE", 5), ("BR", 4), ("PT", 4), ("DZ", 4)],
}


def flag(nation: str) -> str:
    return NATIONS.get(nation, ("🏳️", "EN"))[0]


def random_nation(rng: random.Random, league_nation: str) -> str:
    mix = LEAGUE_MIX.get(league_nation, LEAGUE_MIX["UA"])
    n = rng.choices([n for n, _ in mix], weights=[w for _, w in mix])[0]
    if n == "AF":
        n = rng.choice(["SN", "CI", "NG", "GH", "CM", "ML", "GN"])
    return n


def random_name(rng: random.Random, nation: str = "UA") -> str:
    if nation == "AF":
        nation = rng.choice(["SN", "CI", "NG", "GH"])
    pool_key = NATIONS.get(nation, ("", "EN"))[1]
    first, last = POOLS.get(pool_key, POOLS["EN"])
    return f"{rng.choice(first)} {rng.choice(last)}"
