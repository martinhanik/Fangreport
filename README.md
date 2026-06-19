# Fangreport

## Beschreibung

Viele Angler denken darüber nach, Fangbuch zu führen. Die meisten geben das Vorhaben aber schnell wieder auf, weil das 
manuelle Zusammentragen von Umweltbedingungen eine mühsame Aufgabe ist. Hier setzt *Fangreport* an. Es erstellt nach 
Eingabe weniger Eckdaten vollautomatisch Fangreports mit reichen Details zu Umweltbedingungen. So werden u. a.
Temperatur, Luftdruck, Regen, Windgeschwindigkeit, Mondphase und Pegelstände erfasst und in leicht verständlicher Weise 
dargestellt. So kann man erst verlässlich feststellen, ob die Zielfische ein erkennbares Fressmuster haben. Aber auch, 
wenn es um das Festhalten von Erinnerungen geht, hilft *Fangreport* einfach und schnell. 

## Setup

### Voraussetzungen

Installieren Sie [git](https://git-scm.com) auf dem Computer. 

Fangreport benötigt eine virtuelle Umgebung mit den folgenden Python-Paketen:
* numpy,
* pandas,
* requests,
* matplotlib,
* typer.


### Repository

Klonen Sie das Repository in einen lokalen Ordner, indem sie diesen im Terminal öffnen und folgenden Befehl eingeben:

```
git clone git@github.com:martinhanik/Fangbuch.git
```

Gehen Sie nun in das Repository. Wurde dieses unter dem Standard-Ordnernamen angelegt, lautet der Befehl:

```
cd Fangbuch
```

Sie können nun eine virtuelle Umgebung mit dem Befehl

```
python -m venv .venv
```

anlegen.

Aktivieren Sie die Umgebung bei jeder Nutzung durch den Befehl

```
source .venv/bin/activate
```

Die benötigten Pakete werden einmal durch folgenden Befehl installiert:

```
pip install -r requirements.txt
```

## Nutzung

Die Erstellung eines Reports ist mithilfe einer GUI möglich. Sie lässt sich mit dem Befehl

```
python -m fangreport.gui
```

starten. Die GUI erlaubt es, alle relevanten Angaben zu einem Fang zu erfassen. Notwendige Angaben 
sind mit einem Stern (*) markiert. 

Mit dem folgenden Befehl lässt sich ein Fangreport in der Konsole erstellen:

```
#  Das Datum muss innerhalb der letzten 30 Tage liegen.
python -m fangreport.client --Fischart Wels --Länge 130 --Gewicht 13 --Datum 2026-05-22 --Zeit 20:00 --Breitengrad 49.357599616156776 --Längengrad 8.494281048199765 --Pegelstation Speyer --Wassertemperatur 12.5 --Trübung klar 
```

Hier wurde am 22.5.2026 um 20 Uhr ein Wels von 130 cm und 13 kg gefangen. Die Koordinaten des Fangorts (am Rhein) 
sind (49.357599616156776, 8.494281048199765). Die Messstation, von der der Pegel abgefragt werden soll, ist Speyer. 
Zum Zeitpunkt des Fangs war das Wasser klar und hatte eine Temperatur von 12,5 Grad Celsius. Der Ordnerpfad zu einem 
Fangfoto könnte noch mit dem Argument `--Fotopfad` angegeben werden. 

Die Argumente `--Länge`, `--Wassertemperatur`, `--Trübung` und `--Fotopfad` sind optionale Parameter. Ein fertiger 
Fangreport wird im Ordner `Fänge` gespeichert.

Fangreporte können für deutsche Pegelstationen bis zu 30 Tage rückwirkend erstellt werden. Eine Liste aller Pegelstellen 
findet sich auf der [Pegelonline-Webseite](https://pegelonline.wsv.de/gast/start).

Zusätzlich unterstützt Fangreport erste Pegelstationen in Italien:

am Po
* **Piacenza**,
* Cremona,
* **Casalmaggiore**,
* **Boretto**,
* Borgoforte,
* Sermide e Felonica/Castelmassa,
* **Pontelagoscuro**,
* **Polesella**,
* **Cavanella**;

am Mincio
* **Peschiera del Garda**,
* Monzambano,
* **Goito**,
* **Lago Superiore**,
* **Lago di Mezzo**,
* **Vallazza**,
* **Governolo**;

und am Oglio
* Marcaria.

Italienische Stationen erlauben es teilweise, einen Report von einem Fang zu erstellen, der mehr als 30 Tage 
zurückliegt.  

Für italienische Stationen versucht Fangreport, Pegeldaten automatisch über die jeweilige regionale Datenquelle 
abzurufen.
Dabei werden die Daten aller fett geschriebenen Stationen über das 
[Portal](https://idrometri.agenziapo.it/Aegis/map/map2d) der *Agenzia Interregionale per il fiume Po (AIPO)* geladen. 
Hierfür braucht es einen gültigen Refresh-Token und eine gültige Client-ID. Diese müssen bei der ersten Nutzung oder 
wenn längere Zeit kein Fangreport erstellt wurde aus einem Browser geladen werden. Man findet sie nach dem Öffnen der 
Seite in den Webinformationen des Entwicklertools. Anschließend müssen die Daten in der JSON-Datei ``aipo_auth.json`` 
in ``fangreport/data`` gespeichert werden. Als Vorlage dient ``aipo_auth_example.json``, das im selben Ordner liegt. 
