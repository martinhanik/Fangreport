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

Fangreport benötigt die folgenden Python-Pakete:
* numpy,
* pandas,
* requests,
* matplotlib.


### Repository

Als Nächstes klonen Sie das Repository in einen lokalen Ordner mit dem Befehl:

```
git clone git@github.com:martinhanik/Fangbuch.git
```

Gehen Sie nun in das Repository. Wurde dieses unter dem Standard-Ordnernamen angelegt, lautet der Befehl:

```
cd Fangbuch
```

## Nutzung

Mit dem folgenden Befehl lässt sich ein Fangreport in der Konsole erstellen:

```
python fangreport.py --Fischart Wels --Länge 130 --Datum 2026-05-22 --Zeit 20:00 --Längengrad 52.477575 --Breitengrad 12.449408 --Messstation Tieckow --Wassertemperatur 12.5 --Trübung klar --Fotopfad /Pfad/zum/Fangfoto
```

Hier wurde am 22.5.2026 um 20 Uhr ein Wels von 130 cm gefangen. Die Koordinaten des Fangorts (an der Havel) sind 
(52.477575, 12.449408). Die Messstation, von der der Pegel abgefragt werden soll, ist Tieckow. Zum Zeitpunkt des Fangs 
war das Wasser klar und hatte eine Temperatur von 12,5 Grad Celsius. Der Speicherort eines Fangfotos wird ebenfalls 
angegeben. Länge, Wassertemperatur, Trübung und der Fotopfad sind optionale Parameter. Wenn keine Wassertemperatur 
angegeben wird, versucht Fangreport, die Wassertemperatur automatisch über PEGELONLINE abzurufen. Die fertigen 
Fangreporte werden im Ordner `Fänge` gespeichert.

Die Erstellung eines Reports ist auch mithilfe einer GUI möglich. Sie lässt sich mit dem Befehl

```
python fangreport.py 
```

starten. Die GUI erlaubt es, alle relevanten Angaben zu einem Fang zu erfassen. Notwendige Angaben 
sind mit einem Stern (*) markiert. 


Fangreporte können bis zu 30 Tage rückwirkend erstellt werden. Eine Liste aller Pegelstellen findet sich auf 
der [Pegelonline-Webseite](https://pegelonline.wsv.de/gast/start).
