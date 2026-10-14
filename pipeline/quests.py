"""Quests: short walks through the city as riddles. Three kinds of step, mixed within a quest:

  find    a riddle; the player finds the building on the map and clicks it. Hints first draw a circle around it,
          then name the street; "Show me" flies there for no tiles.
  year    the map flies to a building and hides its age (colours and card); the player guesses the year it was built.
  choice  the map flies to a building; the player picks one of three answers.
  where   a photo and a name; the player taps the map where it stands and scores by distance.

Every claim rests on a source that s13_quests.py checks: an article that must contain the given strings, or a story
of a context layer already checked by s08_curated. Where a step names a year, that year must also be the map's year
for the building, so the card the player opens next tells the same story.

`at` says where the step happens:
  "wd:<article>"            the building(s) the article's Wikidata item names (BAG id, P5208)
  "story:<layer>:<address>" the buildings of that curated story
  "addr:<address>"          an address, geocoded to its BAG building
  "rule:oldest"             the oldest building with an exact year, from the map's own data
`checks`: [(article, [strings])]: each article must contain each string (case-insensitive).
`clue`: "today" (the building's photo), or an archive photo {"id", "thumb", "year"} from the Stadsarchief.
Levels: 1 easy, 2 medium, 3 hard. Persecution and the Holocaust are deliberately not made into a game.
"""


def T(en, nl):
    return dict(en=en, nl=nl)


def find(at, riddle, hints, reveal, checks=(), clue=None, mode=None, layer=None):
    return dict(kind="find", at=at, riddle=riddle, hints=hints, reveal=reveal, checks=list(checks), clue=clue,
                mode=mode, layer=layer)


def year(at, ask, answer, reveal, checks):
    return dict(kind="year", at=at, ask=ask, year=answer, reveal=reveal, checks=list(checks))


def choice(at, ask, options, reveal, checks=()):
    """options: the right answer first; the page shuffles them."""
    return dict(kind="choice", at=at, ask=ask, options=options, reveal=reveal, checks=list(checks))


def where(at, name, reveal, checks):
    """A photo and a name; the player taps the map where they think it stands and scores by distance."""
    return dict(kind="where", at=at, riddle=T(f"Where is {name[0]}?", f"Waar staat {name[1]}?"), reveal=reveal,
                checks=list(checks), clue="today")


def archive(id, thumb, year):
    return dict(id=id, thumb=thumb, year=year)


QUESTS = [
    # ---------------------------------------------------------------- easy
    dict(id="where", level=1,
         title=T("Where is it?", "Waar staat het?"),
         intro=T("Eight famous buildings. Tap the map where you think each one stands: the closer, the more points.",
                 "Acht bekende gebouwen. Tik op de kaart waar je denkt dat ze staan: hoe dichterbij, hoe meer punten."),
         steps=[
             where("wd:nl:Station Amsterdam Centraal", ("Centraal Station", "het Centraal Station"),
                   T("Opened on 15 October 1889, on three artificial islands in the IJ.",
                     "Geopend op 15 oktober 1889, op drie kunstmatige eilanden in het IJ."),
                   [("nl:Station Amsterdam Centraal", ["15 oktober 1889", "drie kunstmatige eilanden"])]),
             where("wd:nl:Westerkerk (Amsterdam)", ("the Westerkerk", "de Westerkerk"),
                   T("On the Prinsengracht. Rembrandt was buried here in 1669; nobody knows where his grave is.",
                     "Aan de Prinsengracht. Rembrandt werd hier in 1669 begraven; niemand weet waar zijn graf ligt."),
                   [("nl:Westerkerk (Amsterdam)", ["Prinsengracht", "plaats van het graf onbekend"])]),
             where("addr:Museumstraat 1", ("the Rijksmuseum", "het Rijksmuseum"),
                   T("Pierre Cuypers' building, home of the museum since 1885.",
                     "Het gebouw van Pierre Cuypers, sinds 1885 het onderkomen van het museum."),
                   [("nl:Rijksmuseum Amsterdam", ["sinds 1885 gevestigd in het Rijksmuseumgebouw", "Pierre Cuypers"])]),
             where("wd:nl:Koninklijk Theater Carré", ("Carré", "Carré"),
                   T("On the Amstel. It opened on 3 December 1887 as Oscar Carré's stone circus.",
                     "Aan de Amstel. Het opende op 3 december 1887 als het stenen circus van Oscar Carré."),
                   [("nl:Koninklijk Theater Carré", ["3 december 1887", "Oscar Carré", "Amstel"])]),
             where("wd:nl:Zuiderkerk (Amsterdam)", ("the Zuiderkerk", "de Zuiderkerk"),
                   T("Near the Nieuwmarkt: the first church in Amsterdam designed for Protestant worship, in use from 1611.",
                     "Bij de Nieuwmarkt: de eerste kerk in Amsterdam die voor de protestantse eredienst werd "
                     "ontworpen, in gebruik vanaf 1611."),
                   [("nl:Zuiderkerk (Amsterdam)", ["eerste voor de protestantse eredienst", "1611"])]),
             where("wd:nl:Amstel Hotel", ("the Amstel Hotel", "het Amstel Hotel"),
                   T("On the Amstel by the Sarphatistraat. In use since the summer of 1867, the first hotel of "
                     "international standing in Amsterdam.",
                     "Aan de Amstel bij de Sarphatistraat. In gebruik sinds de zomer van 1867, de eerste "
                     "logeergelegenheid op internationaal niveau in Amsterdam."),
                   [("nl:Amstel Hotel", ["zomer van 1867", "Sarphatistraat",
                                         "eerste logeergelegenheid op internationaal niveau"])]),
             where("wd:nl:12-verdiepingenhuis", ("the Wolkenkrabber", "de Wolkenkrabber"),
                   T("In the Rivierenbuurt: twelve storeys of flats from 1932.",
                     "In de Rivierenbuurt: twaalf verdiepingen woningen uit 1932."),
                   [("nl:12-verdiepingenhuis", ["Rivierenbuurt", "uit 1932"])]),
             where("wd:nl:De Dageraad (Amsterdam)", ("De Dageraad", "De Dageraad"),
                   T("In Plan Zuid: 294 homes and six shops by Michel de Klerk and Piet Kramer, for a socialist "
                     "housing association.",
                     "In Plan Zuid: 294 woningen en zes winkels van Michel de Klerk en Piet Kramer, voor een "
                     "socialistische woningbouwvereniging."),
                   [("nl:De Dageraad (Amsterdam)", ["294 woningen en zes winkels", "Plan Zuid", "socialistische"])]),
         ]),
    dict(id="dam", level=1,
         title=T("Around the Dam", "Rond de Dam"),
         intro=T("Five buildings within a few minutes' walk of the city's main square. A gentle start.",
                 "Vijf gebouwen op een paar minuten lopen van het belangrijkste plein van de stad. Een rustig begin."),
         steps=[
             find("wd:nl:Paleis op de Dam",
                  T("Start at the heart of the city. Find the town hall that was so grand a king later moved in.",
                    "Begin in het hart van de stad. Zoek het stadhuis dat zo groots was dat er later een koning introk."),
                  [T("It fills one whole side of the Dam square.", "Het beslaat een hele kant van de Dam.")],
                  T("The Royal Palace. Built 1648–1665 as the town hall, on 13,659 wooden piles; Louis Napoleon, "
                    "king of Holland, made it his palace in 1808.",
                    "Het Koninklijk Paleis. Gebouwd in 1648–1665 als stadhuis, op 13.659 houten palen; Lodewijk "
                    "Napoleon, koning van Holland, maakte er in 1808 zijn paleis van."),
                  checks=[("nl:Paleis op de Dam", ["13.659", "Lodewijk Napoleon", "1648 en 1665"])], clue="today"),
             choice("wd:nl:Nieuwe Kerk (Amsterdam)",
                    T("The church beside the palace has a royal role. Which one?",
                      "De kerk naast het paleis heeft een koninklijke rol. Welke?"),
                    [T("Kings and queens are inaugurated here", "Koningen en koninginnen worden hier ingehuldigd"),
                     T("Kings and queens are buried here", "Koningen en koninginnen worden hier begraven"),
                     T("Parliament opens its year here", "Het parlement opent hier zijn jaar")],
                    T("Inaugurations, since William I, then sovereign prince, swore his oath on the constitution here "
                      "in 1814. The royal crypt is in another Nieuwe Kerk: the one in Delft.",
                      "Inhuldigingen, sinds Willem I, toen soeverein vorst, hier in 1814 de eed op de grondwet "
                      "aflegde. De koninklijke grafkelder ligt in een andere Nieuwe Kerk: die van Delft."),
                    checks=[("nl:Nieuwe Kerk (Amsterdam)", ["30 maart 1814", "inhuldigingen"]),
                            ("nl:Nieuwe Kerk (Delft)", ["grafkelder van het Koninklijk Huis"])]),
             choice("wd:nl:Station Amsterdam Centraal",
                    T("The palace stands on 13,659 wooden piles. How many hold up Centraal Station?",
                      "Het paleis staat op 13.659 houten palen. Op hoeveel palen staat het Centraal Station?"),
                    [T("8,687", "8.687"), T("2,186", "2.186"), T("31,000", "31.000")],
                    T("8,687, driven into three artificial islands in the IJ. The station cut the old harbour front "
                      "off from open water. (2,186 is the Concertgebouw.)",
                      "8.687, geslagen in drie kunstmatige eilanden in het IJ. Het station sneed het oude havenfront "
                      "af van het open water. (2.186 is het Concertgebouw.)"),
                    checks=[("nl:Station Amsterdam Centraal", ["8.687", "drie kunstmatige eilanden"]),
                            ("nl:Concertgebouw (Amsterdam)", ["2186 heipalen"])]),
             year("wd:nl:Beurs van Berlage",
                  T("Berlage's exchange on the Damrak: plain brick after a century of ornament. When was it finished?",
                    "Berlages beurs aan het Damrak: kale baksteen na een eeuw ornament. Wanneer was hij klaar?"),
                  1903,
                  T("1903, after five years of building. It is seen as a forerunner of the Amsterdam School, which was "
                    "also partly a reaction against its strictness.",
                    "1903, na vijf jaar bouwen. Hij geldt als voorloper van de Amsterdamse School, die deels ook een "
                    "reactie was op zijn strengheid."),
                  checks=[("nl:Beurs van Berlage", ["1898-1903", "voorloper van zowel het nieuwe bouwen, als de "
                                                    "Amsterdamse School", "reactie op de strenge Beurs"])]),
             find("wd:nl:Magna Plaza",
                  T("Behind the palace stands a palace for letters: a neo-Gothic main post office with pointed "
                    "towers. Today people go there to shop.",
                    "Achter het paleis staat een paleis voor brieven: een neogotisch hoofdpostkantoor met spitse "
                    "torens. Nu gaan mensen er winkelen."),
                  [T("It is on the Nieuwezijds Voorburgwal, right behind the palace.",
                     "Het staat aan de Nieuwezijds Voorburgwal, vlak achter het paleis.")],
                  T("The old main post office, 1895–1899, now the Magna Plaza shopping centre.",
                    "Het oude hoofdpostkantoor, 1895–1899, nu winkelcentrum Magna Plaza."),
                  checks=[("nl:Magna Plaza", ["1895-1899", "Hoofdpostkantoor", "winkelcentrum"])]),
         ]),
    dict(id="tiny", level=1,
         title=T("Tiny, narrow, crooked", "Klein, smal en scheef"),
         intro=T("The odd ones: the smallest, the narrowest, the bent and the hidden.",
                 "De vreemde eend: de kleinste, de smalste, de geknikte en de verborgene."),
         steps=[
             find("story:secrets:Oude Hoogstraat 22",
                  T("2.02 metres wide and 5 metres deep. Find the house often called the smallest in Amsterdam.",
                    "2,02 meter breed en 5 meter diep. Zoek het huis dat vaak het kleinste van Amsterdam heet."),
                  [T("It is on the Oude Hoogstraat, between the Dam and the Nieuwmarkt, next to the old East India "
                     "House.",
                     "Het staat in de Oude Hoogstraat, tussen de Dam en de Nieuwmarkt, naast het oude Oost-Indisch "
                     "Huis.")],
                  T("Oude Hoogstraat 22.", "Oude Hoogstraat 22.")),
             find("story:secrets:Singel 7",
                  T("The narrowest house front in Amsterdam. Behind it, the house widens.",
                    "De smalste gevel van Amsterdam. Daarachter wordt het huis breder."),
                  [T("It is at the very start of the Singel, a few minutes from Centraal Station.",
                     "Het staat helemaal aan het begin van het Singel, een paar minuten van het Centraal Station.")],
                  T("Singel 7, the narrowest front in the city.", "Singel 7, de smalste gevel van de stad.")),
             choice("story:secrets:Keizersgracht 123",
                    T("Six heads stare from this front. Legend says they are burglars, beheaded one by one by the "
                      "maid. Who are they really?",
                      "Zes hoofden kijken vanaf deze gevel. Volgens de legende zijn het inbrekers, een voor een "
                      "onthoofd door de dienstmeid. Wie zijn het echt?"),
                    [T("Six classical gods", "Zes klassieke goden"), T("Six burgomasters", "Zes burgemeesters"),
                     T("The builder's six sons", "De zes zonen van de bouwer")],
                    T("Busts of six classical gods. The House with the Heads.",
                      "Bustes van zes klassieke goden. Het Huis met de Hoofden.")),
             find("story:secrets:Herengracht 170",
                  T("This front bends twice so that it can follow the curve of its canal.",
                    "Deze gevel knikt twee keer om de bocht van zijn gracht te volgen."),
                  [T("It is on the Herengracht, where the canal bends between the Raadhuisstraat and the Leliegracht.",
                     "Het staat aan de Herengracht, waar de gracht buigt tussen de Raadhuisstraat en de Leliegracht.")],
                  T("The Bartolotti House, around 1617.", "Huis Bartolotti, rond 1617."),
                  checks=[("nl:Huis Bartolotti", ["twee knikken", "1617"])], clue="today"),
             find("story:secrets:Begijnhof 34",
                  T("One of the city's last wooden houses, from about 1528, hides in a courtyard behind a gate off "
                    "the Spui.",
                    "Een van de laatste houten huizen van de stad, van rond 1528, verstopt zich op een hof achter "
                    "een poort aan het Spui."),
                  [T("The courtyard is the Begijnhof.", "Het hof is het Begijnhof.")],
                  T("Het Houten Huis, Begijnhof 34.", "Het Houten Huys, Begijnhof 34."),
                  checks=[("nl:Begijnhof (Amsterdam)", ["Begijnhof 34", "1528"])]),
             choice("story:secrets:Oudezijds Voorburgwal 38",
                    T("In 1661 a stocking merchant bought this canal house and built something in its attics. What?",
                      "In 1661 kocht een kousenkoopman dit grachtenhuis en bouwde iets op de zolders. Wat?"),
                    [T("A Catholic church", "Een katholieke kerk"), T("A synagogue", "Een synagoge"),
                     T("A press for banned books", "Een drukkerij voor verboden boeken")],
                    T("A Catholic church, at a time when Catholics could not worship in public: Our Lord in the "
                      "Attic.",
                      "Een katholieke kerk, in een tijd dat katholieken niet openlijk mochten kerken: Ons' Lieve Heer "
                      "op Solder.")),
         ]),
    # ---------------------------------------------------------------- medium
    dict(id="rembrandt", level=2,
         title=T("Rembrandt's city", "De stad van Rembrandt"),
         intro=T("Where he lived, what he drew, where he went broke and where he was buried.",
                 "Waar hij woonde, wat hij tekende, waar hij failliet ging en waar hij begraven werd."),
         steps=[
             find("wd:nl:Rembrandthuis",
                  T("In 1639 he bought a house on the Jodenbreestraat for 13,000 guilders. Nineteen years later, "
                    "bankrupt, he lost it. Find it.",
                    "In 1639 kocht hij een huis in de Jodenbreestraat voor 13.000 gulden. Negentien jaar later, "
                    "failliet, raakte hij het kwijt. Zoek het."),
                  [T("The Jodenbreestraat runs from the Zuiderkerk to the Waterlooplein market.",
                     "De Jodenbreestraat loopt van de Zuiderkerk naar de markt op het Waterlooplein.")],
                  T("The Rembrandt House. After his bankruptcy it was auctioned in 1658, for 11,000 guilders.",
                    "Het Rembrandthuis. Na zijn faillissement werd het in 1658 geveild, voor 11.000 gulden."),
                  checks=[("nl:Rembrandthuis", ["dertienduizend", "faillissement", "elfduizend", "1658"])],
                  clue="today"),
             find("wd:nl:Zuiderkerk (Amsterdam)",
                  T("A few steps from his door rises the first church Amsterdam designed for Protestant worship, in "
                    "use from 1611.",
                    "Een paar stappen van zijn deur staat de eerste kerk die Amsterdam ontwierp voor de protestantse "
                    "eredienst, in gebruik vanaf 1611."),
                  [T("Its tall tower stands just north of the Jodenbreestraat.",
                     "De hoge toren staat net ten noorden van de Jodenbreestraat.")],
                  T("The Zuiderkerk, begun in 1603.", "De Zuiderkerk, begonnen in 1603."),
                  checks=[("nl:Zuiderkerk (Amsterdam)", ["eerste voor de protestantse eredienst", "1611", "1603"])]),
             find("story:secrets:Nieuwmarkt 4",
                  T("Upstairs in this old city gate the surgeons met; he painted their anatomy lesson.",
                    "Boven in deze oude stadspoort vergaderden de chirurgijns; hij schilderde hun anatomische les."),
                  [T("It stands like a small castle in the middle of the Nieuwmarkt.",
                     "Het staat als een kasteeltje midden op de Nieuwmarkt.")],
                  T("De Waag: a city gate of 1488, later the weigh house.",
                    "De Waag: een stadspoort uit 1488, later het waaggebouw.")),
             choice("wd:nl:Montelbaanstoren",
                    T("He drew this tower in 1644. What is missing from his drawing?",
                      "Hij tekende deze toren in 1644. Wat ontbreekt er op zijn tekening?"),
                    [T("The spire Hendrick de Keyser put on it in 1606", "De spits die Hendrick de Keyser er in 1606 op zette"),
                     T("The clock", "De klok"), T("The water in front of it", "Het water ervoor")],
                    T("The spire. He drew the tower without the crown De Keyser had added in 1606.",
                      "De spits. Hij tekende de toren zonder de bekroning die De Keyser er in 1606 op had gezet."),
                    checks=[("nl:Montelbaanstoren", ["tekende de toren in 1644, maar zonder de opbouw van De Keyser",
                                                    "1606"])]),
             choice("wd:nl:Westerkerk (Amsterdam)",
                    T("He was buried in this church in 1669. Where exactly is his grave?",
                      "Hij werd in 1669 in deze kerk begraven. Waar ligt zijn graf precies?"),
                    [T("Nobody knows", "Niemand weet het"), T("Under the pulpit", "Onder de preekstoel"),
                     T("At the foot of the tower", "Aan de voet van de toren")],
                    T("Nobody knows. A memorial was put up by the north aisle in 1906.",
                      "Niemand weet het. In 1906 kwam er een gedenkteken bij de noordelijke zijbeuk."),
                    checks=[("nl:Westerkerk (Amsterdam)", ["plaats van het graf onbekend", "1906"])]),
         ]),
    dict(id="companies", level=2,
         title=T("Ships, spices and companies", "Schepen, specerijen en compagnieën"),
         intro=T("The trade that made the Golden Age, and its darker side, in five buildings.",
                 "De handel die de Gouden Eeuw maakte, en de schaduwkant ervan, in vijf gebouwen."),
         steps=[
             find("story:asia:Oude Hoogstraat 24",
                  T("Find the headquarters of the Dutch East India Company, the VOC, built in 1604.",
                    "Zoek het hoofdkantoor van de Verenigde Oost-Indische Compagnie, de VOC, gebouwd in 1604."),
                  [T("It is on the Oude Hoogstraat, by the Kloveniersburgwal.",
                     "Het staat aan de Oude Hoogstraat, bij de Kloveniersburgwal.")],
                  T("The East India House.", "Het Oost-Indisch Huis."),
                  checks=[("nl:Oost-Indisch Huis", ["gebouwd 1604"])]),
             find("story:atlantic:Herenmarkt 99",
                  T("The other company sailed west. The West India Company, which ran the slave trade and the colony of New "
                    "Netherland, met here from 1623 to 1647.",
                    "De andere compagnie voer naar het westen. De West-Indische Compagnie, die de slavenhandel en de "
                    "kolonie Nieuw-Nederland dreef, vergaderde hier van 1623 tot 1647."),
                  [T("It stands on the Herenmarkt, a square by the Brouwersgracht.",
                     "Het staat aan de Herenmarkt, een pleintje bij de Brouwersgracht.")],
                  T("The West India House.", "Het West-Indisch Huis.")),
             choice("wd:nl:Schreierstoren",
                    T("On 4 April 1609 Henry Hudson sailed from this tower for the VOC. What was he sent to find?",
                      "Op 4 april 1609 vertrok Henry Hudson bij deze toren voor de VOC. Wat moest hij vinden?"),
                    [T("A western passage to the Indies", "Een westelijke doorvaart naar Indië"),
                     T("Whaling grounds off Spitsbergen", "Walvisgronden bij Spitsbergen"),
                     T("Gold on the coast of Africa", "Goud aan de kust van Afrika")],
                    T("A western passage to the Indies. A plaque on the tower, given by a historical society in "
                      "New York, remembers the voyage.",
                      "Een westelijke doorvaart naar Indië. Een plaquette op de toren, geschonken door een "
                      "historisch genootschap uit New York, herinnert aan de reis."),
                    checks=[("nl:Schreierstoren", ["4 april 1609", "westelijke doorvaart naar Indië", "New York"])]),
             choice("wd:nl:Trippenhuis",
                    T("Two brothers built this palace: two whole houses behind one front. Its chimneys are shaped "
                      "like mortars. Why?",
                      "Twee broers bouwden dit paleis: twee hele huizen achter één gevel. De schoorstenen hebben de "
                      "vorm van mortieren. Waarom?"),
                    [T("They got rich trading arms", "Ze werden rijk met wapenhandel"),
                     T("They commanded the city's guns", "Ze voerden het bevel over het stadsgeschut"),
                     T("Mortar chimneys were the fashion", "Mortierschoorstenen waren in de mode")],
                    T("The Trip brothers made their fortune from arms; the chimneys point to their trade.",
                      "De broers Trip verdienden hun fortuin met wapens; de schoorstenen verwijzen naar hun handel."),
                    checks=[("nl:Trippenhuis", ["twee volledige huizen achter een gemeenschappelijke voorgevel",
                                               "hoekschoorstenen in de vorm van mortieren"])]),
             find("story:asia:Prins Hendrikkade 108",
                  T("Six shipping companies that sailed to the Indies shared one office from 1913. It is called the "
                    "first building wholly in the Amsterdam School style.",
                    "Zes rederijen die op Indië voeren deelden vanaf 1913 één kantoor. Het heet het eerste gebouw "
                    "geheel in de stijl van de Amsterdamse School."),
                  [T("It stands on a point of land on the Prins Hendrikkade, east of Centraal Station.",
                     "Het staat op een punt aan de Prins Hendrikkade, ten oosten van het Centraal Station.")],
                  T("The Scheepvaarthuis, now a hotel.", "Het Scheepvaarthuis, nu een hotel."),
                  checks=[("nl:Scheepvaarthuis", ["zes Amsterdamse rederijen", "eerste gebouw dat geheel in de stijl "
                                                  "van de Amsterdamse School"])]),
         ]),
    dict(id="brick", level=2,
         title=T("Red brick dreams", "Dromen in rode baksteen"),
         intro=T("The Amsterdam School and the new city of the 1920s, out beyond the canals.",
                 "De Amsterdamse School en de nieuwe stad van de jaren twintig, voorbij de grachten."),
         steps=[
             find("addr:Oostzaanstraat 45",
                  T("Workers' housing by Michel de Klerk, built 1914–1921. People named it after its shape.",
                    "Arbeiderswoningen van Michel de Klerk, gebouwd in 1914–1921. De volksmond noemde het naar de "
                    "vorm."),
                  [T("It is in the Spaarndammerbuurt, west of the centre, by the railway.",
                     "Het staat in de Spaarndammerbuurt, ten westen van het centrum, bij het spoor.")],
                  T("Het Schip, the Ship, now the museum of the Amsterdam School.",
                    "Het Schip, nu het museum van de Amsterdamse School."),
                  checks=[("nl:Museum Het Schip", ["1914-1921", "Het Schip"])]),
             year("wd:nl:12-verdiepingenhuis",
                  T("Amsterdam's first tower of flats, nicknamed the Skyscraper: twelve storeys, when the rules "
                    "allowed four. When was it built?",
                    "De eerste woontoren van Amsterdam, bijgenaamd De Wolkenkrabber: twaalf verdiepingen, toen de "
                    "regels er vier toestonden. Wanneer is hij gebouwd?"),
                  1932,
                  T("1932, by J.F. Staal. The building rules had to be changed first.",
                    "1932, door J.F. Staal. Eerst moest de bouwverordening worden aangepast."),
                  checks=[("nl:12-verdiepingenhuis", ["uit 1932", "maximaal vier woonlagen",
                                                      "eerste van dat type in Amsterdam"])]),
             find("addr:Olympisch Stadion 2",
                  T("At the Games of 1928 a fire burned in a concrete bowl on top of this stadium's tower: the first "
                    "Olympic flame in history.",
                    "Bij de Spelen van 1928 brandde in een betonnen schaal boven op de toren van dit stadion een "
                    "vuur: het eerste olympische vuur in de geschiedenis."),
                  [T("It is in the south-west of the city, at the end of the Stadionweg.",
                     "Het ligt in het zuidwesten van de stad, aan het eind van de Stadionweg.")],
                  T("The Olympic Stadium, by Jan Wils.", "Het Olympisch Stadion, van Jan Wils."),
                  checks=[("nl:Olympisch Stadion (Amsterdam)", ["eerste olympische vuur", "Jan Wils"])]),
             choice("wd:nl:De Bazel (gebouw)",
                    T("This bank headquarters on the Vijzelstraat took from 1919 to 1926 to build. Who works in it "
                      "now?",
                      "Aan dit hoofdkantoor van een bank aan de Vijzelstraat werd van 1919 tot 1926 gebouwd. Wie "
                      "werkt er nu?"),
                    [T("The City Archives", "Het Stadsarchief"), T("The Dutch central bank", "De Nederlandsche Bank"),
                     T("The university library", "De universiteitsbibliotheek")],
                    T("The Stadsarchief, since 2007: the archive whose old photos you can browse in the cards on "
                      "this map.",
                      "Het Stadsarchief, sinds 2007: het archief waarvan je de oude foto's in de kaartjes op deze "
                      "kaart kunt bekijken."),
                    checks=[("nl:De Bazel (gebouw)", ["1919 en 1926", "Sinds 2007 is er het Stadsarchief"])]),
             year("wd:nl:Concertgebouw (Amsterdam)",
                  T("Back to the 19th century for the last one: the concert hall on 2,186 piles. When did it open?",
                    "Voor de laatste terug naar de negentiende eeuw: de concertzaal op 2186 palen. Wanneer ging hij "
                    "open?"),
                  1888,
                  T("On 11 April 1888.", "Op 11 april 1888."),
                  checks=[("nl:Concertgebouw (Amsterdam)", ["geopend op 11 april 1888", "2186 heipalen"])]),
         ]),
    # ---------------------------------------------------------------- hard
    dict(id="then", level=3,
         title=T("Then and now", "Toen en nu"),
         intro=T("Six photos from the city archive, 1950–1953. No names, no text: find each building as it "
                 "stands today.",
                 "Zes foto's uit het Stadsarchief, 1950–1953. Geen namen, geen tekst: vind elk gebouw zoals het er "
                 "nu staat."),
         steps=[
             find("wd:nl:Paleis op de Dam",
                  T("Lit up at night, seen from a hotel across the square.",
                    "'s Avonds verlicht, gezien vanuit een hotel aan de overkant van het plein."),
                  [T("The square is the Dam.", "Het plein is de Dam.")],
                  T("The Royal Palace, 1952.", "Het Koninklijk Paleis, 1952."),
                  clue=archive("b17df159-1b9f-ad04-ab2f-d7ab3106ffeb", "7968494b-6308-cc73-2ef5-d52467fa7493", 1952)),
             find("wd:nl:Schreierstoren",
                  T("A round brick tower by the water's edge.", "Een ronde bakstenen toren aan het water."),
                  [T("It stands on the Prins Hendrikkade, near Centraal Station.",
                     "Hij staat aan de Prins Hendrikkade, bij het Centraal Station.")],
                  T("The Schreierstoren, around 1487, in 1950.", "De Schreierstoren, rond 1487, in 1950."),
                  clue=archive("a87756a3-4e1f-af65-a924-40d80355ad24", "7fbed6ac-c725-10a8-d4dd-de0c20db48d1", 1950)),
             find("wd:nl:Koninklijk Theater Carré",
                  T("A long white building across a wide river, seen from a bridge.",
                    "Een lang wit gebouw aan een brede rivier, gezien vanaf een brug."),
                  [T("The river is the Amstel; the bridge is the Hoge Sluis.",
                     "De rivier is de Amstel; de brug is de Hoge Sluis.")],
                  T("Carré, built as a stone circus in 1887.", "Carré, in 1887 gebouwd als stenen circus."),
                  checks=[("nl:Koninklijk Theater Carré", ["3 december 1887", "Oscar Carré"])],
                  clue=archive("22491164-a156-11e4-8ca4-9367051b6c01", "328e5cbc-1a08-cb7b-1637-106c11b3027e", 1953)),
             find("wd:nl:Montelbaanstoren",
                  T("A tower with a pointed crown at the end of a long, straight canal.",
                    "Een toren met een spitse bekroning aan het eind van een lange, rechte gracht."),
                  [T("The canal is the Oudeschans, east of the Nieuwmarkt.",
                     "De gracht is de Oudeschans, ten oosten van de Nieuwmarkt.")],
                  T("The Montelbaanstoren.", "De Montelbaanstoren."),
                  clue=archive("042aec7f-4d0a-c571-d0e2-d6994b44c3c2", "05eff68b-0365-ab7b-b7c7-07a3d43357cb", 1953)),
             find("wd:nl:Krijtberg",
                  T("Two slender church towers squeezed between canal houses.",
                    "Twee slanke kerktorens tussen grachtenhuizen geperst."),
                  [T("The canal is the Singel, a short walk from the Spui.",
                     "De gracht is het Singel, op een paar minuten van het Spui.")],
                  T("De Krijtberg, a neo-Gothic Jesuit church begun in 1881.",
                    "De Krijtberg, een neogotische jezuïetenkerk, begonnen in 1881."),
                  checks=[("nl:Krijtberg", ["In 1881 begonnen", "neogotische", "jezuïeten"])],
                  clue=archive("705d6256-8527-11e4-9411-6f3b4156ffed", "56e134e4-4265-a557-0508-099ade3c1ae1", 1953)),
             find("wd:nl:12-verdiepingenhuis",
                  T("A lonely tower of flats, far from the canals.", "Een eenzame woontoren, ver van de grachten."),
                  [T("It is in the south, on a square in the Rivierenbuurt.",
                     "Hij staat in het zuiden, aan een plein in de Rivierenbuurt.")],
                  T("The Wolkenkrabber, 1932.", "De Wolkenkrabber, 1932."),
                  clue=archive("701eca1e-8527-11e4-bc53-5b87fa8df581", "608b012f-8ee6-184f-6414-a160f0027bab", 1953)),
         ]),
    dict(id="map", level=3,
         title=T("Read the map", "Lees de kaart"),
         intro=T("No riddles about history this time: the answers are in the map's colours and shapes.",
                 "Deze keer geen raadsels over geschiedenis: de antwoorden zitten in de kleuren en vormen van de "
                 "kaart."),
         steps=[
             find("rule:oldest",
                  T("Find the oldest building standing in Amsterdam.",
                    "Zoek het oudste gebouw dat in Amsterdam nog staat."),
                  [T("Colour the map by period and look for the darkest colour in the old centre.",
                     "Kleur de kaart naar periode en zoek de donkerste kleur in het oude centrum.")],
                  T("The Oude Kerk, consecrated in 1306: the oldest building in the city.",
                    "De Oude Kerk, gewijd in 1306: het oudste gebouw van de stad."),
                  checks=[("nl:Oude Kerk (Amsterdam)", ["oudste nog bestaande gebouw van Amsterdam", "1306"])],
                  mode="period"),
             find("addr:Amstelplein 1",
                  T("Find the tallest building in Amsterdam. Chimneys do not count.",
                    "Zoek het hoogste gebouw van Amsterdam. Schoorstenen tellen niet mee."),
                  [T("Colour the map by floors and look south-east, by Amstel station.",
                     "Kleur de kaart naar verdiepingen en kijk naar het zuidoosten, bij station Amstel.")],
                  T("The Rembrandt Tower: 150 metres with its 15-metre antenna, the tallest skyscraper in Amsterdam, "
                    "opened in 1995. (The spike in the western docks is the 175-metre chimney of the Hemweg power station.)",
                    "De Rembrandttoren: 150 meter met zijn antenne van 15 meter, de hoogste wolkenkrabber van "
                    "Amsterdam, geopend in 1995. (De piek in het Westelijk Havengebied is de schoorsteen van 175 "
                    "meter van de Hemwegcentrale.)"),
                  checks=[("nl:Rembrandttoren", ["hoogste wolkenkrabber van Amsterdam", "15 meter hoge antenne 150 meter",
                                                 "1995", "Amstelstation"]),
                          ("nl:Centrale Hemweg", ["De schoorsteen is 175 meter hoog"])], mode="floors"),
             find("story:secrets:Funenkade 5",
                  T("A windmill in the middle of the city: two wooden octagons stacked on a brick base.",
                    "Een molen midden in de stad: twee houten achtkanten op een stenen voet."),
                  [T("It stands on the Funenkade, east of the old centre.",
                     "Hij staat aan de Funenkade, ten oosten van het oude centrum.")],
                  T("De Gooyer.", "De Gooyer.")),
             year("wd:nl:Noorderkerk (Amsterdam)",
                  T("A church for the poor of the Jordaan, in the shape of a Greek cross. Guess its year without the "
                    "colours.",
                    "Een kerk voor de armen van de Jordaan, in de vorm van een Grieks kruis. Raad het jaar zonder "
                    "de kleuren."),
                  1622,
                  T("Built 1620–1623.", "Gebouwd in 1620–1623."),
                  checks=[("nl:Noorderkerk (Amsterdam)", ["tussen 1620 en 1623", "Grieks kruis"])]),
         ]),
]
