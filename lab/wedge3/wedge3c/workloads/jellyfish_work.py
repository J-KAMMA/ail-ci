"""jellyfish workload: jaro_winkler, levenshtein, soundex over a word list.

Pure mode imports the 0.8.9 package (its C extension is removed by the harness); native
mode imports jellyfish 1.x, which is Rust.  The output is a deterministic summary plus the
exact values for a small sample, so a byte difference is visible.
"""
import jellyfish

WORDS = """
the quick brown fox jumps over lazy dog algorithm library approximate phonetic matching
smith johnson williams brown jones garcia miller davis rodriguez martinez hernandez lopez
gonzalez wilson anderson thomas taylor moore jackson martin lee perez thompson white harris
sanchez clark ramirez lewis robinson walker young allen king wright scott torres nguyen hill
flores green adams nelson baker hall rivera campbell mitchell carter roberts gomez phillips
evans turner diaz parker cruz edwards collins reyes stewart morris morales murphy cook rogers
gutierrez ortiz morgan cooper peterson bailey reed kelly howard ramos kim cox ward richardson
watson brooks chavez wood james bennett gray mendoza ruiz hughes price alvarez castillo
sanders patel myers long ross foster jimenez powell jenkins perry russell sullivan bell
coleman butler henderson barnes gonzales fisher vasquez simmons romero jordan patterson
alexander hamilton graham reynolds griffin wallace moreno west cole hayes bryant herrera
gibson ellis tran medina aguilar stevens murray ford castro marshall owens harrison fernandez
mcdonald woods washington kennedy wells vargas henry chen freeman webb tucker guzman burns
crawford olson simpson porter hunter gordon mendez silva shaw snyder mason dixon munoz hunt
hicks holmes palmer wagner black robertson boyd rose stone salazar fox warren mills meyer
rice schmidt garza daniels ferguson nichols stephens soto weaver ryan gardner payne grant
dunn kelley spencer hawkins arnold pierce vazquez hansen peters santos hart bradley knight
elliott cunningham duncan armstrong hudson carroll lane riley andrews alvarado delgado berry
perkins hoffman johnston matthews pena richards contreras willis carpenter lawrence sandoval
guerrero george chapman rios estrada ortega watkins greene nunez wheeler valdez harper burke
larson santiago maldonado morrison franklin carlson austin dominguez carr lawson jacobs
obrien lynch singh vega bishop montgomery oliver jensen harvey williamson gilbert dean sims
espinoza howell wong reid hanson le mccoy garrett burton fuller wang weber welch rojas lucas
marquez fields park yang little banks padilla day walsh bowman schultz luna fowler mejia
davidson acosta brewer may holland juarez newman pearson curtis cortez douglas schneider
barrett navarro figueroa keller avila wade molina stanley hopkins campos barnett bates
chambers caldwell beck lambert miranda byrd craig ayala lowe frazier powers neal leonard
gregory carrillo sutton fleming rhodes shelton schwartz norris jennings watts duran walters
cohen mcdaniel moran parks steele vaughn becker holt deleon barker norris benson neal
dominguez horton terry wolfe hale lyons graves haynes miles moody dyer castaneda banks
""".split()

LIMIT = 150000


def main():
    words = WORDS
    n = len(words)
    lev_total = 0
    soundex_total = 0
    jw_total = 0.0
    sample = []
    for i in range(LIMIT):
        a = words[(i * 7) % n]
        b = words[(i * 13 + 5) % n]
        lv = jellyfish.levenshtein_distance(a, b)
        jw = jellyfish.jaro_winkler_similarity(a, b)
        sx = jellyfish.soundex(a)
        lev_total += lv
        jw_total += jw
        soundex_total += ord(sx[0]) * 31 + len(sx)
        if i < 12:
            sample.append("%s %s %d %.17g %s" % (a, b, lv, jw, sx))
    print("words %d pairs %d" % (n, LIMIT))
    print("levenshtein total %d" % lev_total)
    print("jaro_winkler total %.17g" % jw_total)
    print("soundex total %d" % soundex_total)
    for row in sample:
        print(row)


main()
