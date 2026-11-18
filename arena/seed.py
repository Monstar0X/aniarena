"""Bundled starter catalog (own-words teasers) so the bot works offline and before the first AniList sync.
Live data from AniList replaces it automatically (see catalog.py)."""
from __future__ import annotations

# id|title|aliases|year|season|episodes|format|score|studio|genres|tags|teaser
_RAW = """
1535|Death Note|dn|2006|FAL|37|TV|84|Madhouse|Mystery,Psychological,Supernatural,Thriller|Detective,Crime,Philosophy|A brilliant student finds a notebook that kills anyone whose name is written in it, and a famous detective hunts him down.
5114|Fullmetal Alchemist: Brotherhood|fmab;fullmetal alchemist brotherhood|2009|SPR|64|TV|91|Bones|Action,Adventure,Drama,Fantasy|Alchemy,Military,Brothers|Two brothers use forbidden alchemy to restore their bodies and uncover a nation-wide conspiracy.
16498|Attack on Titan|aot;snk;shingeki no kyojin|2013|SPR|25|TV|85|Wit Studio|Action,Drama,Fantasy,Mystery|Gore,Military,Tragedy|Humanity hides behind enormous walls from giants that devour people, until the walls are breached.
101922|Demon Slayer|kny;kimetsu no yaiba|2019|SPR|26|TV|83|ufotable|Action,Fantasy|Demons,Swordplay,Family|A kind boy becomes a swordsman to cure his sister, who was turned into a demon.
21087|One Punch Man|opm|2015|FAL|12|TV|83|Madhouse|Action,Comedy,Sci-Fi|Super Power,Parody|A hero who can defeat anyone with a single hit is bored by how easy winning has become.
20|Naruto||2002|FAL|220|TV|80|Pierrot|Action,Adventure,Fantasy|Ninja,Shounen|An outcast ninja boy dreams of becoming the leader of his village.
1735|Naruto Shippuden|shippuden|2007|WIN|500|TV|84|Pierrot|Action,Adventure,Fantasy|Ninja,Shounen|The grown-up ninja returns from training to face a criminal organisation hunting powerful creatures.
269|Bleach||2004|FAL|366|TV|79|Pierrot|Action,Adventure,Supernatural|Shinigami,Swordplay|A teenager who can see ghosts inherits the powers of a spirit reaper to protect the living.
21|One Piece|op|1999|FAL|1100|TV|88|Toei Animation|Action,Adventure,Comedy,Fantasy|Pirates,Shounen|A rubber-limbed young man sails with a crew in search of the legendary treasure that will make him king of pirates.
11061|Hunter x Hunter (2011)|hxh;hunter x hunter|2011|FAL|148|TV|90|Madhouse|Action,Adventure,Fantasy|Shounen,Super Power|A boy takes the licensing exam to become an elite adventurer in hopes of finding his missing father.
1|Cowboy Bebop||1998|SPR|26|TV|86|Sunrise|Action,Adventure,Sci-Fi|Space,Bounty Hunter|A ragtag crew of bounty hunters chases criminals across the solar system while running from their pasts.
30|Neon Genesis Evangelion|nge;eva|1995|FAL|26|TV|83|Gainax|Action,Drama,Mecha,Psychological,Sci-Fi|Mecha,Philosophy|Teenagers pilot giant bio-machines to fight mysterious beings attacking a futuristic city.
1575|Code Geass: Lelouch of the Rebellion|code geass|2006|FAL|25|TV|86|Sunrise|Action,Drama,Mecha,Sci-Fi|Military,Strategy|An exiled prince gains a mind-control power and leads a rebellion against an empire.
21459|My Hero Academia|mha;boku no hero academia|2016|SPR|13|TV|78|Bones|Action,Comedy|Super Power,School,Shounen|In a world where nearly everyone has powers, a powerless boy inherits the strongest hero's ability.
113415|Jujutsu Kaisen|jjk|2020|FAL|24|TV|85|MAPPA|Action,Fantasy,Supernatural|Curses,Shounen|A student swallows a cursed object and joins a school of sorcerers to fight deadly spirits.
140960|Spy x Family|spy family|2022|SPR|12|TV|84|Wit Studio|Action,Comedy|Espionage,Family Life,Wholesome|A spy, an assassin and a telepathic girl pretend to be a normal family, each hiding the truth from the others.
154587|Frieren: Beyond Journey's End|sousou no frieren;frieren|2023|FAL|28|TV|91|Madhouse|Adventure,Drama,Fantasy|Elf,Coming of Age|After the hero's party defeats the demon king, a long-lived mage sets out to understand the friends she left behind.
21507|Mob Psycho 100||2016|SUM|12|TV|86|Bones|Action,Comedy,Supernatural|Super Power,Coming of Age|A quiet middle schooler with overwhelming psychic power tries to live a normal life.
20464|Haikyu!!|haikyuu|2014|SPR|25|TV|85|Production I.G|Comedy,Drama,Sports|Volleyball,School Club|A short boy with huge ambition joins the volleyball team that once made it to the national stage.
20665|Your Lie in April|shigatsu wa kimi no uso|2014|FAL|22|TV|86|A-1 Pictures|Drama,Music,Romance|Classical Music,Tragedy|A prodigy who lost the ability to hear his own piano is pulled back by a free-spirited violinist.
21827|Violet Evergarden||2018|WIN|13|TV|85|Kyoto Animation|Drama,Fantasy,Slice of Life|Post-War,Letters|A former soldier becomes a ghostwriter to understand the meaning of the last words she was given.
4224|Toradora!||2008|FAL|25|TV|82|J.C.Staff|Comedy,Drama,Romance|School,Love Triangle|Two classmates with scary reputations team up to win over each other's crushes.
10087|Fate/Zero||2011|FAL|13|TV|83|ufotable|Action,Fantasy|Magic,Tournament|Seven mages summon legendary heroes to fight over a wish-granting relic.
11757|Sword Art Online|sao|2012|SUM|25|TV|72|A-1 Pictures|Action,Adventure,Fantasy,Romance|Virtual World,Video Games|Thousands of players are trapped in a virtual reality game where dying means dying for real.
22319|Tokyo Ghoul||2014|SUM|12|TV|74|Pierrot|Action,Drama,Horror,Mystery|Gore,Psychological|A student barely survives an attack and becomes half-ghoul, caught between two worlds.
813|Dragon Ball Z|dbz|1989|SPR|291|TV|82|Toei Animation|Action,Adventure,Fantasy|Martial Arts,Super Power|Earth's strongest fighters defend the planet from alien warriors in escalating battles.
21355|Re:ZERO -Starting Life in Another World-|re zero;rezero|2016|SPR|25|TV|83|White Fox|Drama,Fantasy,Psychological,Thriller|Isekai,Time Loop|A shut-in dragged to a fantasy world discovers he returns to life after every death.
21202|KonoSuba|konosuba gods blessing on this wonderful world|2016|WIN|10|TV|82|Studio Deen|Adventure,Comedy,Fantasy|Isekai,Parody|A man reincarnated in a fantasy world is stuck with a useless goddess and a very unhelpful party.
20832|Overlord||2015|SUM|13|TV|77|Madhouse|Action,Adventure,Fantasy|Isekai,Video Games|A player stays logged in when his favourite game shuts down and finds himself ruling as an undead king.
101348|Vinland Saga||2019|SUM|24|TV|87|Wit Studio|Action,Adventure,Drama|Vikings,Historical|A young warrior follows a band of mercenaries in search of the man who killed his father.
127230|Chainsaw Man|csm|2022|FAL|12|TV|85|MAPPA|Action,Fantasy,Horror|Gore,Devils|A broke young man merges with his chainsaw-devil pet and joins a government devil-hunting squad.
130003|Bocchi the Rock!|bocchi|2022|FAL|12|TV|87|CloverWorks|Comedy,Music,Slice of Life|Band,Gag Humor|An extremely shy girl who plays guitar alone is dragged into a real band.
97986|Made in Abyss||2017|SUM|13|TV|86|Kinema Citrus|Adventure,Drama,Fantasy,Mystery|Survival,Tragedy|An orphan descends into a vast, deadly chasm to find her mother.
918|Gintama||2006|SPR|201|TV|87|Sunrise|Action,Comedy,Sci-Fi|Parody,Samurai|A lazy samurai takes odd jobs in an Edo overrun by aliens.
13601|Psycho-Pass||2012|FAL|22|TV|82|Production I.G|Action,Psychological,Sci-Fi|Dystopian,Police|In a future where a system scores everyone's potential to commit crime, an inspector questions justice.
9253|Steins;Gate|steins gate|2011|SPR|24|TV|87|White Fox|Drama,Sci-Fi,Thriller|Time Travel,Conspiracy|A self-proclaimed mad scientist discovers a way to send messages to the past with terrifying consequences.
97940|Black Clover||2017|FAL|170|TV|77|Pierrot|Action,Adventure,Comedy,Fantasy|Magic,Shounen|A boy born without magic in a world of mages vows to become the Wizard King.
105333|Dr. Stone||2019|SUM|24|TV|83|TMS Entertainment|Adventure,Comedy,Sci-Fi|Survival,Science|After humanity is turned to stone for millennia, a genius sets out to rebuild civilisation with science.
105310|Fire Force|enen no shouboutai|2019|SUM|24|TV|77|David Production|Action,Comedy,Supernatural|Firefighters,Super Power|A young man with a flaming-footed power joins a squad that fights people who burst into flames.
14719|JoJo's Bizarre Adventure|jjba|2012|FAL|26|TV|79|David Production|Action,Adventure,Supernatural|Super Power,Family|A bloodline's fight against an immortal vampire plays out across generations with outrageous poses.
101921|Kaguya-sama: Love Is War|kaguya sama|2019|WIN|12|TV|84|A-1 Pictures|Comedy,Psychological,Romance|School,Mind Games|Two brilliant student council leaders each try to trick the other into confessing first.
124080|Horimiya||2021|WIN|13|TV|82|CloverWorks|Comedy,Romance,Slice of Life|School,Wholesome|Two classmates discover each other's secret sides outside of school.
21519|Your Name.|kimi no na wa|2016|SUM|1|MOVIE|87|CoMix Wave Films|Drama,Romance,Supernatural|Body Swapping,Tragedy|Two teenagers who have never met start swapping bodies and trying to find each other.
199|Spirited Away|sen to chihiro|2001|SUM|1|MOVIE|87|Studio Ghibli|Adventure,Fantasy,Supernatural|Spirits,Coming of Age|A girl wanders into a spirit world and must work in a bathhouse to save her parents.
164|Princess Mononoke|mononoke hime|1997|SUM|1|MOVIE|85|Studio Ghibli|Action,Adventure,Fantasy|Nature,Historical|A cursed prince is caught between a forest's gods and an iron-making town.
20954|A Silent Voice|koe no katachi|2016|SUM|1|MOVIE|89|Kyoto Animation|Drama,Romance|Bullying,Disability|A former bully tries to make amends with a deaf girl he once tormented.
19|Monster||2004|SPR|74|TV|88|Madhouse|Drama,Mystery,Psychological,Thriller|Crime,Detective|A surgeon who saved a boy's life spends years hunting the killer that boy grew into.
22535|Parasyte -the maxim-|parasyte;kiseijuu|2014|FAL|24|TV|83|Madhouse|Action,Horror,Psychological,Sci-Fi|Body Horror,Gore|A teenager shares his body with an alien parasite that took over his hand instead of his brain.
28223|Death Parade||2015|WIN|12|TV|79|Madhouse|Mystery,Psychological,Thriller|Afterlife,Game|Dead strangers are forced into deadly games that judge whether they deserve rebirth or the void.
31043|Erased|boku dake ga inai machi|2016|WIN|12|TV|83|A-1 Pictures|Mystery,Psychological,Supernatural,Thriller|Time Travel,Detective|A man who rewinds time just before disasters is sent back to his childhood to stop a kidnapper.
6702|Fairy Tail||2009|SUM|175|TV|76|A-1 Pictures|Action,Adventure,Comedy,Fantasy|Magic,Guild|A celestial wizard joins a rowdy magic guild and its fire-breathing mage.
47|Akira||1988|SUM|1|MOVIE|80|TMS Entertainment|Action,Sci-Fi|Cyberpunk,Post-Apocalyptic|In a ruined future Tokyo a biker gang member develops terrifying psychic power.
4181|Clannad: After Story||2008|FAL|24|TV|90|Kyoto Animation|Drama,Romance,Slice of Life|Family Life,Tragedy|The story of a delinquent student and the girl he loves continues past school into adult life.
171018|Dandadan||2024|FAL|12|TV|85|Science SARU|Action,Comedy,Supernatural|Aliens,Ghost|A girl who believes in ghosts and a boy who believes in aliens each try to prove the other wrong.
151807|Solo Leveling||2024|WIN|12|TV|83|A-1 Pictures|Action,Adventure,Fantasy|Dungeon,Super Power|The weakest hunter gains the ability to level up endlessly after surviving a deadly dungeon.
150672|Oshi no Ko||2023|SPR|11|TV|84|Doga Kobo|Drama,Mystery,Supernatural|Idols,Reincarnation|A doctor is reborn as the child of his favourite idol and gets drawn into the dark side of entertainment.
120377|Cyberpunk: Edgerunners||2022|FAL|10|ONA|86|Trigger|Action,Sci-Fi|Cyberpunk,Tragedy|A street kid in a neon megacity becomes a mercenary after losing everything.
137822|Blue Lock||2022|FAL|24|TV|82|8bit|Sports|Football,Psychological|Strikers are locked in a facility to forge the most selfish striker in the world.
153518|Delicious in Dungeon|dungeon meshi|2024|WIN|24|TV|87|Trigger|Adventure,Comedy,Fantasy|Food,Dungeon|Adventurers descend into a dungeon and survive by cooking the monsters they defeat.
""".strip()

_SEASON = {"WIN": "WINTER", "SPR": "SPRING", "SUM": "SUMMER", "FAL": "FALL"}


def seed_docs() -> list[dict]:
    docs = []
    for i, line in enumerate(_RAW.splitlines()):
        mid, title, aliases, year, season, eps, fmt, score, studio, genres, tags, desc = line.split("|")
        docs.append({
            "_id": int(mid), "title": title, "aliases": [a for a in aliases.split(";") if a],
            "year": int(year), "season": _SEASON[season], "episodes": int(eps), "format": fmt,
            "score": int(score), "popularity": 200000 - i * 2500, "studio": studio,
            "genres": genres.split(","), "tags": tags.split(","), "desc": desc, "cover": None, "src": "seed",
        })
    return docs
