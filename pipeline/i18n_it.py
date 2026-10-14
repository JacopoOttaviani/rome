"""Italian versions of every text the pipeline writes: layer titles, intros, caveats, group labels, sources.

Keyed by the English text. s05_layers.py adds a `<field>_it` next to each field it finds here, and reports
the English texts that have no Italian version yet.
"""

IT = {
    # sections
    "Architecture": "Architettura",
    "Faith and power": "Fede e potere",
    "The city": "La città",
    "Ancient Rome": "Roma antica",

    # eras
    "1500–1960": "1500–1960", "300–today": "300–oggi", "All periods": "Tutte le epoche", "1929–today": "1929–oggi",
    "1000s–1921": "XI secolo–1921", "Antiquity–today": "Antichità–oggi",

    # architects
    "Architects": "Architetti",
    "A handful of names drew the Rome that visitors photograph. Bramante and Michelangelo set the Renaissance on the Vatican hill; Della Porta and Maderno finished their domes and facades; Bernini and Borromini, rivals for forty years, made the city Baroque; Carlo Fontana carried it into the 1700s. Three centuries later Marcello Piacentini drew the university, Via della Conciliazione and much of EUR.":
        "Pochi nomi hanno disegnato la Roma che i visitatori fotografano. Bramante e Michelangelo portano il Rinascimento sul colle Vaticano; Della Porta e Maderno ne completano cupole e facciate; Bernini e Borromini, rivali per quarant'anni, fanno barocca la città; Carlo Fontana la accompagna nel Settecento. Tre secoli dopo Marcello Piacentini disegna la Città universitaria, via della Conciliazione e gran parte dell'EUR.",
    "Buildings whose Wikidata item names the architect (P84); a building can have several.":
        "Edifici il cui elemento Wikidata indica l'architetto (P84); un edificio può averne più d'uno.",
    "Wikidata, architect (P84)": "Wikidata, architetto (P84)",
    "Bramante": "Bramante", "Michelangelo": "Michelangelo", "Giacomo Della Porta": "Giacomo Della Porta",
    "Carlo Maderno": "Carlo Maderno", "Gian Lorenzo Bernini": "Gian Lorenzo Bernini",
    "Francesco Borromini": "Francesco Borromini", "Carlo Fontana": "Carlo Fontana",
    "Marcello Piacentini": "Marcello Piacentini",

    # styles
    "Architecture styles": "Stili architettonici",
    "Rome rebuilt itself in every style it invented or borrowed: the basilicas of the first Christians, Romanesque bell towers, Renaissance palaces, a Baroque that remade whole streets, the revivals and eclectic palazzi of the new capital, Liberty villas, and the rationalism of the 1930s.":
        "Roma si è ricostruita in ogni stile che ha inventato o preso in prestito: le basiliche dei primi cristiani, i campanili romanici, i palazzi del Rinascimento, un Barocco che ha rifatto strade intere, i revival e i palazzi eclettici della nuova capitale, i villini Liberty e il razionalismo degli anni Trenta.",
    "Buildings whose Wikidata item names an architectural style (P149).":
        "Edifici il cui elemento Wikidata indica uno stile architettonico (P149).",
    "Wikidata, architectural style (P149)": "Wikidata, stile architettonico (P149)",
    "Early Christian and Romanesque": "Paleocristiano e romanico", "Renaissance": "Rinascimento",
    "Mannerism": "Manierismo", "Baroque and Rococo": "Barocco e rococò", "Neoclassicism": "Neoclassicismo",
    "Revivals and eclecticism": "Revival ed eclettismo", "Art Nouveau (Liberty)": "Liberty",
    "Rationalism and modern": "Razionalismo e moderno",

    # heritage
    "Protected heritage": "Patrimonio tutelato",
    "Italy protects its cultural property building by building; the historic centre of Rome, the properties of the Holy See within it and the basilica of Saint Paul are a UNESCO World Heritage Site since 1980.":
        "L'Italia tutela i suoi beni culturali edificio per edificio; il centro storico di Roma, le proprietà della Santa Sede che vi si trovano e la basilica di San Paolo sono patrimonio mondiale dell'UNESCO dal 1980.",
    "Buildings whose Wikidata item records a heritage designation (P1435); far from every protected building in Rome has one.":
        "Edifici il cui elemento Wikidata registra una tutela (P1435); non tutti gli edifici tutelati di Roma ce l'hanno.",
    "Wikidata, heritage designation (P1435)": "Wikidata, status di patrimonio (P1435)",
    "Part of the UNESCO World Heritage Site": "Parte del sito UNESCO", "National monument": "Monumento nazionale",
    "Italian cultural property": "Bene culturale italiano",

    # faith
    "Churches and convents": "Chiese e conventi",
    "Rome holds more than nine hundred churches: the four papal basilicas, the titular churches of the cardinals, the national churches of every Catholic nation, and the parish churches the city built as it grew. Convents and colleges of the religious orders fill whole blocks of the centre.":
        "Roma conta più di novecento chiese: le quattro basiliche papali, i titoli cardinalizi, le chiese nazionali di ogni paese cattolico e le parrocchie costruite man mano che la città cresceva. Conventi e collegi degli ordini religiosi occupano isolati interi del centro.",
    "Use and type as the 2014 regional survey records them, where a church and its convent are often one building; basilicas from Wikidata.":
        "Uso e tipologia come li registra il rilievo regionale del 2014, dove chiesa e convento sono spesso un solo edificio; le basiliche da Wikidata.",
    "Regione Lazio, DBGT 2014": "Regione Lazio, DBGT 2014",
    "Basilica": "Basilica", "Church, convent or bell tower": "Chiesa, convento o campanile",

    # holy see
    "The Vatican and the embassies": "Il Vaticano e le ambasciate",
    "Since the Lateran Treaty of 1929 the Vatican City is a state of its own inside Rome. Rome is also the only city with two diplomatic corps: embassies to Italy and embassies to the Holy See, many of them in palaces of the centre and villas of Parioli.":
        "Dai Patti Lateranensi del 1929 la Città del Vaticano è uno Stato a sé dentro Roma. Roma è anche l'unica città con due corpi diplomatici: le ambasciate presso l'Italia e quelle presso la Santa Sede, molte in palazzi del centro e ville dei Parioli.",
    "The Vatican's buildings carry no Italian municipality code in the regional survey; embassies are its use 'sede ambasciata o consolato'.":
        "Gli edifici del Vaticano non hanno codice comunale italiano nel rilievo regionale; le ambasciate sono quelli con uso 'sede ambasciata o consolato'.",
    "Vatican City": "Città del Vaticano", "Embassy or consulate": "Ambasciata o consolato",

    # rioni
    "The rioni": "I rioni",
    "Papal Rome was divided into fourteen rioni, a name from the regiones of Augustus. When the city became Italy's capital in 1871 it filled the vineyards inside the Aurelian walls and spilled beyond them; eight new rioni were drawn between 1874 and 1921, from Esquilino to Prati.":
        "La Roma dei papi era divisa in quattordici rioni, nome che viene dalle regiones di Augusto. Diventata capitale d'Italia nel 1871, la città riempì le vigne dentro le Mura Aureliane e le superò; tra il 1874 e il 1921 nacquero otto nuovi rioni, dall'Esquilino a Prati.",
    "Rioni boundaries from OpenStreetMap.": "Confini dei rioni da OpenStreetMap.",
    "OpenStreetMap contributors, ODbL": "Contributori di OpenStreetMap, ODbL",
    "The fourteen rioni of papal Rome": "I quattordici rioni della Roma papale",
    "The eight rioni of the new capital": "Gli otto rioni della nuova capitale",

    # ancient
    "Monuments and ruins": "Monumenti e rovine",
    "Ancient Rome still stands among the houses: the Colosseum, the Pantheon, the Theatre of Marcellus, tombs along the consular roads, aqueduct arches in the eastern suburbs. Alongside them are the monuments and fountains the popes and the kings of Italy added.":
        "La Roma antica è ancora in piedi tra le case: il Colosseo, il Pantheon, il Teatro di Marcello, i sepolcri lungo le consolari, gli archi degli acquedotti nella periferia est. Accanto, i monumenti e le fontane aggiunti dai papi e dai re d'Italia.",
    "Dated to antiquity: a Wikidata item says so. Ruins and monuments as the 2014 survey draws them; a ruin can also be a farmhouse abandoned last century.":
        "Datati all'antichità: lo dice un elemento Wikidata. Rovine e monumenti come li disegna il rilievo del 2014; un rudere può anche essere un casale abbandonato nel secolo scorso.",
    "Regione Lazio, DBGT 2014; Wikidata": "Regione Lazio, DBGT 2014; Wikidata",
    "Standing since antiquity": "In piedi dall'antichità", "Monument": "Monumento", "Ruin": "Rudere",
    "Fountain": "Fontana",
}
