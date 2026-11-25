"""Real-football positions, formations with pitch coordinates, and positional familiarity."""
from __future__ import annotations

import random

# role -> (line, ukrainian name)
ROLES = {
    "GK": ("GK", "Воротар"),
    "CB": ("DF", "Центральний захисник"),
    "LB": ("DF", "Лівий захисник"),
    "RB": ("DF", "Правий захисник"),
    "LWB": ("DF", "Лівий вінгбек"),
    "RWB": ("DF", "Правий вінгбек"),
    "CDM": ("MF", "Опорний півзахисник"),
    "CM": ("MF", "Центральний півзахисник"),
    "CAM": ("MF", "Атакувальний півзахисник"),
    "LM": ("MF", "Лівий півзахисник"),
    "RM": ("MF", "Правий півзахисник"),
    "LW": ("FW", "Лівий вінгер"),
    "RW": ("FW", "Правий вінгер"),
    "CF": ("FW", "Другий нападник"),
    "ST": ("FW", "Центральний нападник"),
}

# formation -> list of (role, x%, y%) ; y=0 is the opponent goal line, y=100 our goal line
FORMATIONS = {
    "4-3-3": [("GK", 50, 92), ("LB", 14, 72), ("CB", 37, 76), ("CB", 63, 76), ("RB", 86, 72),
              ("CM", 26, 50), ("CDM", 50, 56), ("CM", 74, 50), ("LW", 16, 24), ("ST", 50, 16), ("RW", 84, 24)],
    "4-2-3-1": [("GK", 50, 92), ("LB", 14, 72), ("CB", 37, 76), ("CB", 63, 76), ("RB", 86, 72),
                ("CDM", 36, 57), ("CDM", 64, 57), ("LW", 16, 34), ("CAM", 50, 36), ("RW", 84, 34), ("ST", 50, 14)],
    "4-4-2": [("GK", 50, 92), ("LB", 14, 72), ("CB", 37, 76), ("CB", 63, 76), ("RB", 86, 72),
              ("LM", 14, 46), ("CM", 38, 50), ("CM", 62, 50), ("RM", 86, 46), ("ST", 36, 18), ("ST", 64, 18)],
    "4-1-4-1": [("GK", 50, 92), ("LB", 14, 72), ("CB", 37, 76), ("CB", 63, 76), ("RB", 86, 72),
                ("CDM", 50, 60), ("LM", 14, 40), ("CM", 37, 44), ("CM", 63, 44), ("RM", 86, 40), ("ST", 50, 15)],
    "3-5-2": [("GK", 50, 92), ("CB", 26, 75), ("CB", 50, 78), ("CB", 74, 75), ("LWB", 10, 50),
              ("CM", 32, 50), ("CDM", 50, 58), ("CM", 68, 50), ("RWB", 90, 50), ("ST", 36, 18), ("ST", 64, 18)],
    "3-4-3": [("GK", 50, 92), ("CB", 26, 75), ("CB", 50, 78), ("CB", 74, 75), ("LM", 12, 48),
              ("CM", 38, 52), ("CM", 62, 52), ("RM", 88, 48), ("LW", 18, 22), ("ST", 50, 16), ("RW", 82, 22)],
    "5-3-2": [("GK", 50, 92), ("LWB", 10, 64), ("CB", 30, 76), ("CB", 50, 79), ("CB", 70, 76), ("RWB", 90, 64),
              ("CM", 28, 48), ("CDM", 50, 54), ("CM", 72, 48), ("ST", 36, 18), ("ST", 64, 18)],
    "4-5-1": [("GK", 50, 92), ("LB", 14, 72), ("CB", 37, 76), ("CB", 63, 76), ("RB", 86, 72),
              ("LM", 11, 42), ("CM", 31, 47), ("CDM", 50, 57), ("CM", 69, 47), ("RM", 89, 42), ("ST", 50, 15)],
}

# how well a player of role A plays in slot B (missing pairs fall back to line-based values)
_NEAR = {
    ("CB", "LB"): .86, ("CB", "RB"): .86, ("LB", "RB"): .9, ("LB", "LWB"): .97, ("RB", "RWB"): .97,
    ("LWB", "LM"): .92, ("RWB", "RM"): .92, ("LB", "LM"): .85, ("RB", "RM"): .85, ("LWB", "RWB"): .88,
    ("CB", "CDM"): .86, ("CDM", "CM"): .95, ("CM", "CAM"): .94, ("CDM", "CAM"): .85, ("LM", "RM"): .9,
    ("LM", "LW"): .95, ("RM", "RW"): .95, ("LW", "RW"): .92, ("LM", "CM"): .88, ("RM", "CM"): .88,
    ("CAM", "CF"): .93, ("CF", "ST"): .97, ("LW", "ST"): .86, ("RW", "ST"): .86, ("CAM", "LW"): .88,
    ("CAM", "RW"): .88, ("LW", "CF"): .88, ("RW", "CF"): .88, ("CAM", "ST"): .84,
}


def line_of(role: str) -> str:
    return ROLES.get(role, ("MF",))[0]


def familiarity(player_role: str, slot_role: str) -> float:
    if player_role == slot_role:
        return 1.0
    if player_role == "GK" or slot_role == "GK":
        return 0.4
    v = _NEAR.get((player_role, slot_role)) or _NEAR.get((slot_role, player_role))
    if v:
        return v
    return 0.78 if line_of(player_role) == line_of(slot_role) else 0.62


ROLE_WEIGHTS = {
    "GK": [("GK", 1)],
    "DF": [("CB", 5), ("LB", 2), ("RB", 2), ("LWB", .4), ("RWB", .4)],
    "MF": [("CM", 4), ("CDM", 2.5), ("CAM", 2), ("LM", 1), ("RM", 1)],
    "FW": [("ST", 4), ("LW", 2.5), ("RW", 2.5), ("CF", .7)],
}


def random_role(rng: random.Random, pos: str) -> str:
    opts = ROLE_WEIGHTS.get(pos, ROLE_WEIGHTS["MF"])
    return rng.choices([r for r, _ in opts], weights=[w for _, w in opts])[0]


def assign_roles(players: list, rng: random.Random) -> None:
    """Give a balanced set of detailed roles to players that only have a line (GK/DF/MF/FW)."""
    seq = {"DF": ["CB", "CB", "LB", "RB", "CB", "LB", "RB", "CB", "RWB", "LWB"],
           "MF": ["CM", "CDM", "CAM", "CM", "LM", "RM", "CDM", "CM", "CAM", "CM"],
           "FW": ["ST", "LW", "RW", "ST", "CF", "LW", "RW", "ST"]}
    by_line: dict[str, list] = {}
    for p in players:
        if not getattr(p, "role", ""):
            by_line.setdefault(p.pos, []).append(p)
    for line, ps in by_line.items():
        if line == "GK":
            for p in ps:
                p.role = "GK"
            continue
        order = seq.get(line, ["CM"])
        rng.shuffle(ps)
        for i, p in enumerate(ps):
            p.role = order[i % len(order)]


DETAILED = {  # football-data.org position strings -> role
    "goalkeeper": "GK", "centre-back": "CB", "left-back": "LB", "right-back": "RB", "defence": "CB",
    "defensive midfield": "CDM", "central midfield": "CM", "attacking midfield": "CAM", "left midfield": "LM",
    "right midfield": "RM", "midfield": "CM", "left winger": "LW", "right winger": "RW", "centre-forward": "ST",
    "second striker": "CF", "offence": "ST",
}


def role_from_text(text: str | None) -> str | None:
    return DETAILED.get((text or "").strip().lower())


# detailed positions for well-known players (others get balanced roles inside their line)
STAR_ROLES = {
    "ST": "Erling Haaland|Harry Kane|Kylian Mbappé|Lautaro Martínez|Alexander Isak|Robert Lewandowski|Serhou Guirassy|"
          "Victor Boniface|Patrik Schick|Benjamin Šeško|Hugo Ekitiké|Marcus Thuram|Romelu Lukaku|Viktor Gyökeres|"
          "Julián Álvarez|Dušan Vlahović|Mateo Retegui|Jonathan David|Ollie Watkins|Dominic Solanke|Artem Dovbyk|"
          "Roman Yaremchuk|Vangelis Pavlidis|Darwin Núñez|Nick Woltemade|Chris Wood|Jean-Philippe Mateta",
    "LW": "Vinícius Júnior|Khvicha Kvaratskhelia|Raphinha|Luis Díaz|Rafael Leão|Gabriel Martinelli|Nico Williams|"
          "Jérémy Doku|Kaoru Mitoma|Leandro Trossard|Karim Adeyemi|Anthony Gordon|Rodrygo|Mykhailo Mudryk",
    "RW": "Lamine Yamal|Mohamed Salah|Bukayo Saka|Ousmane Dembélé|Michael Olise|Désiré Doué|Leroy Sané|Jarrod Bowen|"
          "Bryan Mbeumo|Mohammed Kudus|Federico Chiesa|Antoine Semenyo|Franco Mastantuono",
    "CAM": "Jude Bellingham|Florian Wirtz|Jamal Musiala|Martin Ødegaard|Cole Palmer|Bruno Fernandes|Dani Olmo|"
           "Xavi Simons|Phil Foden|Kevin De Bruyne|Arda Güler|Paulo Dybala|Morgan Gibbs-White|Georgiy Sudakov|"
           "Julian Brandt|Antoine Griezmann|Dominik Szoboszlai|Fermín López|Heorhii Sudakov",
    "CDM": "Rodri|Declan Rice|Moisés Caicedo|Aurélien Tchouaméni|Joshua Kimmich|Stanislav Lobotka|Hakan Çalhanoğlu|"
           "Martín Zubimendi|Granit Xhaka|João Palhinha|Bruno Guimarães|Angelo Stiller|Manuel Ugarte|Casemiro",
    "CM": "Pedri|Vitinha|João Neves|Federico Valverde|Nicolò Barella|Frenkie de Jong|Gavi|Eduardo Camavinga|"
          "Alexis Mac Allister|Ryan Gravenberch|Enzo Fernández|Scott McTominay|Warren Zaïre-Emery|Teun Koopmeiners",
    "CB": "Virgil van Dijk|William Saliba|Marquinhos|Ronald Araújo|Pau Cubarsí|Dean Huijsen|Antonio Rüdiger|"
          "Éder Militão|Dayot Upamecano|Nico Schlotterbeck|Alessandro Bastoni|Gabriel Magalhães|Rúben Dias|"
          "Joško Gvardiol|Mykola Matviyenko|Ibrahima Konaté|Jonathan Tah|Willian Pacho|Micky van de Ven",
    "RB": "Achraf Hakimi|Jules Koundé|Trent Alexander-Arnold|Denzel Dumfries|Jeremie Frimpong|Pedro Porro|"
          "Giovanni Di Lorenzo|Reece James|Ben White",
    "LB": "Nuno Mendes|Federico Dimarco|Alphonso Davies|Theo Hernández|Alejandro Grimaldo|Andrew Robertson|"
          "Alejandro Balde|Milos Kerkez|Riccardo Calafiori|Vitaliy Mykolenko|Álvaro Carreras",
}
_STAR_ROLE = {n.strip().lower(): r for r, names in STAR_ROLES.items() for n in names.split("|")}


def star_role(name: str) -> str | None:
    return _STAR_ROLE.get((name or "").strip().lower())
