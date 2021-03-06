# coding=utf-8
from bs4 import BeautifulSoup
from datetime import date
import mysql.connector
import requests
import re
import constants

# Seperate name from handedness: input e.g. "Travis Wood (L)"
def parsePitcher(combinedString):
    matches = re.search("(.*)\((.*)\)", combinedString)
    return matches.group(1).strip(), matches.group(2).strip()

# Seperate weather data: input e.g. "Gametime Forecast: 76°F • Partly Cloudy • 0% PoP"
def parseWeather(forecastString):
    matches = re.search(":\s(.*)°.*•\s(.*)•\s*(.*)%", forecastString)
    return matches.group(1).strip(), matches.group(2).strip(), matches.group(3).strip()

# Seperate player data: input e.g. "1. Jace Peterson (L) SS"
def parsePlayer(playerString):
    matches = re.search("\.\s*(.*)\s\((.*)\)\s*(.*)", playerString)
    return matches.group(1).strip(), matches.group(2).strip(), matches.group(3).strip()

def getDate(day, month, year, cursor):
    findGame = 'SELECT iddates FROM dates WHERE date = %s'
    findGameData = (date(year, month, day),)
    cursor.execute(findGame, findGameData)

    dateID = -1
    for datez in cursor:
        dateID = datez[0]

    return dateID

def getLineups(day, month, year, url, cursor):

    saveData = []

    # intialize pitchers and batters start and batting order to 0

    queryInitPStart = "UPDATE pitchers SET start = %s"
    StartData = (0,)

    cursor.execute(queryInitPStart, StartData)

    page = requests.get(url)
    soup = BeautifulSoup(page.text, 'html.parser')

    gameID = getDate(day, month, year, cursor)

    # delete from batters daily and pitchers daily b/c we savages

    reInitBattersDaily = "DELETE FROM battersdaily WHERE bgameID = %s"
    reInitBattersDailyD = (gameID,)
    cursor.execute(reInitBattersDaily, reInitBattersDailyD)

    reInitPitchersDaily = "DELETE FROM pitchersdaily WHERE pgameID = %s"
    reInitPitchersDailyD = (gameID,)
    cursor.execute(reInitPitchersDaily, reInitPitchersDailyD)

    games = soup.select(".game")

    for game in games:
        if game.select("div .team-name"):
            gameData = {
                "away" : {
                    "lineup" : []
                },
                "home": {
                    "lineup" : []
                }
            }

            # Team Names
            gameData["away"]["team"] = game.select("div .team-name")[0].string
            awayTeam = game.select("div .team-name")[0].text
            gameData["home"]["team"] = game.select("div .team-name")[1].string
            homeTeam = game.select("div .team-name")[1].text

            if awayTeam == "Diamondbacks":
                awayTeam = "D-backs"
            if homeTeam == "Diamondbacks":
                homeTeam = "D-backs"

            # Starting Pitchers
            awayPitcher, awayPitcherHand = parsePitcher(game.select(".text")[0].select('div')[1].text)
            mlbAPID = game.select(".text")[0].select('div')[1].a['data-mlb']
            gameData["away"]["startingPitcher"] = awayPitcher
            gameData["away"]["startingPitcherHand"] = awayPitcherHand

            homePitcher, homePitcherHand = parsePitcher(game.select(".text")[1].select('div')[1].text)
            mlbHPID = game.select(".text")[1].select('div')[1].a['data-mlb']
            gameData["home"]["startingPitcher"] = homePitcher
            gameData["home"]["startingPitcherHand"] = homePitcherHand

            querySetPStart = "UPDATE pitchers SET start = %s, hand = %s WHERE mlbID = %s"
            playerAPData = (1, awayPitcherHand, int(mlbAPID))
            playerHPData = (1, homePitcherHand, int(mlbHPID))
            cursor.execute(querySetPStart, playerAPData)
            cursor.execute(querySetPStart, playerHPData)

            # get pitcher ids
            queryGetPitcher = "SELECT idpitchers FROM pitchers WHERE mlbID = %s"
            getAwayPitcherData = (mlbAPID,)
            cursor.execute(queryGetPitcher, getAwayPitcherData)

            idAwayPitcher = 0
            for id in cursor:
                idAwayPitcher = id[0]

            getHomePitcherData = (mlbHPID,)
            cursor.execute(queryGetPitcher, getHomePitcherData)

            idHomePitcher = 0
            for id in cursor:
                idHomePitcher = id[0]

            # insert into pitchersdaily
            queryInsertPicher = "INSERT INTO pitchersdaily (pitcherID, pgameID, team, oppTeam) VALUES (%s, %s, %s, %s)"
            pitcherAData = (idAwayPitcher, gameID, awayTeam, homeTeam)
            pitcherHData = (idHomePitcher, gameID, homeTeam, awayTeam)
            cursor.execute(queryInsertPicher, pitcherHData)
            cursor.execute(queryInsertPicher, pitcherAData)

            # Lineups
            awayPlayers = game.select(".team-lineup")[0].select_one(".players").select("div")
            homePlayers = game.select(".team-lineup")[1].select_one(".players").select("div")

            querySetBStart = "UPDATE batters SET start = %s, hand = %s, battingOrder = %s, pos = %s WHERE mlbID = %s"

            # insert into battersdaily
            queryInsertBatterDaily = "INSERT INTO battersdaily (batterID, bgameID, oppPitcher, team, oppTeam) VALUES (%s, %s, %s, %s, %s)"

            # initialize starting batters to 0 for team if lineups are present
            queryBTeam = "SELECT start, battingOrder, mlbID FROM batters WHERE team = %s"
            if homePlayers:
                queryBTeamD = (homeTeam, )
                cursor.execute(queryBTeam, queryBTeamD)

                players = cursor.fetchall()
                for playa in players:
                    queryUpdateStart = "UPDATE batters SET start = %s, battingOrder = %s WHERE mlbID = %s"
                    queryUpdateStartD = (0, 0, int(playa[2]))
                    cursor.execute(queryUpdateStart, queryUpdateStartD)

            if awayPlayers:
                queryBTeamD = (awayTeam,)
                cursor.execute(queryBTeam, queryBTeamD)

                players = cursor.fetchall()
                for playa in players:
                    queryUpdateStart = "UPDATE batters SET start = %s, battingOrder = %s WHERE mlbID = %s"
                    queryUpdateStartD = (0, 0, int(playa[2]))
                    cursor.execute(queryUpdateStart, queryUpdateStartD)

            i = 0
            for player in awayPlayers:
                name, bats, pos = parsePlayer(player.text)
                mlbID = player.a['data-mlb']

                playerData = (1, bats, (i + 1), pos, mlbID)
                cursor.execute(querySetBStart, playerData)

                queryGetBatterID = "SELECT idbatters FROM batters WHERE mlbID = %s"
                getBatterData = (mlbID,)
                cursor.execute(queryGetBatterID, getBatterData)

                idBatter = 0
                for id in cursor:
                    idBatter = id[0]

                batterDailyData = (idBatter, gameID, idHomePitcher, awayTeam, homeTeam)
                try:
                    cursor.execute(queryInsertBatterDaily, batterDailyData)
                except:
                    pass

                gameData["away"]["lineup"].append({
                    "name" : name,
                    "bats" : bats,
                    "pos" : pos
                })
                i = i + 1

            j = 0
            for player in homePlayers:
                name, bats, pos = parsePlayer(player.text)
                mlbID = player.a['data-mlb']

                playerData = (1, bats, (j + 1), pos, mlbID)
                cursor.execute(querySetBStart, playerData)

                queryGetBatterID = "SELECT idbatters FROM batters WHERE mlbID = %s"
                getBatterData = (mlbID,)
                cursor.execute(queryGetBatterID, getBatterData)

                idBatter = 0
                for id in cursor:
                    idBatter = id[0]

                batterDailyData = (idBatter, gameID, idAwayPitcher, homeTeam, awayTeam)

                try:
                    cursor.execute(queryInsertBatterDaily, batterDailyData)
                except:
                    pass

                gameData["home"]["lineup"].append({
                    "name" : name,
                    "bats" : bats,
                    "pos" : pos
                })
                j = j + 1

            saveData.append(gameData)

            # get projected starters if no starting lineup
            if not homePlayers:
                queryGetProjHomePlayers = "SELECT idbatters FROM batters WHERE team = %s and start = %s"
                queryGetProjHomePlayersD = (homeTeam, 1)
                cursor.execute(queryGetProjHomePlayers, queryGetProjHomePlayersD)

                projHomePlayers = cursor.fetchall()

                idBatter = 0
                for projHomePlaya in projHomePlayers:
                    idBatter = projHomePlaya[0]
                    batterDailyData = (idBatter, gameID, idAwayPitcher, homeTeam, awayTeam)
                    try:
                        cursor.execute(queryInsertBatterDaily, batterDailyData)
                    except:
                        pass

            if not awayPlayers:
                queryGetProjAwayPlayers = "SELECT idbatters FROM batters WHERE team = %s and start = %s"
                queryGetProjAwayPlayersD = (awayTeam, 1)
                cursor.execute(queryGetProjAwayPlayers, queryGetProjAwayPlayersD)

                projAwayPlayers = cursor.fetchall()

                idBatter = 0
                for projAwayPlaya in projAwayPlayers:
                    idBatter = projAwayPlaya[0]
                    batterDailyData = (idBatter, gameID, idHomePitcher, awayTeam, homeTeam)
                    try:
                        cursor.execute(queryInsertBatterDaily, batterDailyData)
                    except:
                        pass

    print "Updated Starting Lineups and Batting Order"

if __name__ == "__main__":
    cnx = mysql.connector.connect(user=constants.databaseUser,
                                  host=constants.databaseHost,
                                  database=constants.databaseName,
                                  password=constants.databasePassword)
    cursor = cnx.cursor()

    year = constants.yearP
    month = constants.monthP
    day = constants.dayP

    getLineups(day, month, year, constants.Lineups, cursor)

    cursor.close()
    cnx.commit()
    cnx.close()