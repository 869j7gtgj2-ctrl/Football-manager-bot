from kickoff.realdata import fd_position, match_team, parse_squad

WIKI = """
==Players==
===Current squad===
{{Fs start}}
{{Fs player|no=1|nat=UKR|pos=GK|name=[[Dmytro Riznyk]]}}
{{Fs player|no=5|nat=UKR|pos=DF|name=[[Valeriy Bondar]]|other=[[Captain (association football)|captain]]}}
{{Fs player|no=10|nat=BRA|pos=FW|name=[[Kevin (footballer, born 2003)|Kevin]]}}
{{Fs player|no=27|nat=UKR|pos=MF|name=[[Oleh Ocheretko]]<ref>x</ref>}}
{{Fs end}}
===Out on loan===
{{Fs start}}
{{Fs player|no=—|nat=UKR|pos=FW|name=[[Loan Guy]]}}
{{Fs end}}
"""


def test_parse_wikipedia_squad():
    squad = parse_squad(WIKI)
    names = [p["name"] for p in squad]
    assert names == ["Dmytro Riznyk", "Valeriy Bondar", "Kevin", "Oleh Ocheretko"]
    assert squad[2]["nation"] == "BR" and squad[2]["pos"] == "FW" and squad[2]["number"] == 10
    assert squad[2]["link"] == "Kevin (footballer, born 2003)"


def test_football_data_helpers():
    assert fd_position("Goalkeeper") == "GK" and fd_position("Centre-Back") == "DF"
    assert fd_position("Left Winger") == "FW" and fd_position("Central Midfield") == "MF"
    teams = [{"name": "FC Internazionale Milano", "shortName": "Inter"}, {"name": "AC Milan", "shortName": "Milan"}]
    assert match_team(teams, "ac milan")["shortName"] == "Milan"
    assert match_team(teams, "internazionale")["shortName"] == "Inter"
