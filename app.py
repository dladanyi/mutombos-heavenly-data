import datetime
import json
import os
from http.cookiejar import cut_port_re

import jmespath
import pandas as pd

from flask import Flask, render_template
from yfpy import YahooFantasySportsQuery

from pathlib import Path

from datetime import datetime
import pytz

app = Flask(__name__)

@app.route('/')
def index():

    #print(os.environ)
    league_id=os.environ.get("YAHOO_LEAGUE_ID")
    game_code="nba"

    # configure the Yahoo Fantasy Sports query (change all_output_as_json_str=True if you want to output JSON strings)
    query = YahooFantasySportsQuery(
        league_id=league_id,
        game_code=game_code,
        yahoo_consumer_key=os.environ.get("YAHOO_CONSUMER_KEY"),
        yahoo_consumer_secret=os.environ.get("YAHOO_CONSUMER_SECRET"),
        yahoo_access_token_json=os.environ.get("YAHOO_ACCESS_TOKEN_JSON"),
        env_file_location=Path("."),
        save_token_data_to_env_file=True,
        all_output_as_json_str=False
    )
    #query.save_access_token_data_to_env_file(
    #   env_file_location=Path("."),
    #    save_json_to_var_only=True
    #)

    league_stats_url="https://fantasysports.yahooapis.com/fantasy/v2/league/" + game_code + ".l." + league_id + "/teams/stats"
    season_stats = query.get_response(url=league_stats_url)
    current_week_stats = query.get_response(url=league_stats_url + ";type=week;week=current")

    current_week = jmespath.search('fantasy_content.league[0].current_week', json.loads(season_stats.text))
    last_week = int(current_week) - 1

    # league_settings = query.get_league_settings()

    current_week_rankings = generate_rankings(current_week_stats)
    season_rankings = generate_rankings(season_stats)

    current_week_table_html = current_week_rankings.to_html(
        classes='table table-striped table-hover',
        index=False
    )
    season_table_html = season_rankings.to_html(
        classes='table table-striped table-hover',
        index=False
    )

    last_week_table = None

    if last_week > 0:
        last_week_stats = query.get_response(url=league_stats_url + ";type=week;week=" + str(last_week))
        last_week_rankings = generate_rankings(last_week_stats)
        last_week_table_html = last_week_rankings.to_html(
            classes='table table-striped table-hover',
            index=False
        )



    datetime_pt = datetime.now(pytz.timezone('America/Los_Angeles'))
    formatted_time = datetime_pt.strftime('%a %b %d %Y %H:%M:%S %Z %z')

    # Output 2021:07:08 17:53:23 IST +0530
    # formatted_time = datetime.datetime.now().strftime("%c")
    # print(formatted_time)

    return render_template('table_view_fancy.html',
                           current_week_table=current_week_table_html,
                           season_table=season_table_html,
                           last_week_table=last_week_table_html,
                           current_week = current_week,
                           last_week = str(last_week),
                           formatted_time = formatted_time
                           )


def color_by_rank(val):
    if val == 1:
        return 'background-color: gold'
    elif val == 2:
        return 'background-color: silver'
    elif val == 3:
        return 'background-color: #cd7f32'
    return ''

def generate_rankings(raw_stats):
    stats_json = json.loads(raw_stats.text)

    teams = jmespath.search('fantasy_content.league[1].teams.*.team', stats_json)
    stats_by_team = [{'name': t[0][2]['name'], 'stats': t[1]['team_stats']['stats']} for t in teams]

    df = teams_to_dataframe(stats_by_team)

    #print(df)

    # Create rankings for each stat
    rankings = df[['name']].copy()

    stats_to_rank = ['PTS', 'REB', 'AST', 'ST', 'BLK', '3PTM', 'FG%', 'FT%']
    unranked_stats = [ 'FGM/FGA','FTM/FTA']

    for stat in stats_to_rank:
        rankings[f'{stat}'] = df[stat]
        # Rank each stat (1 = highest)
        rankings[f'{stat}_rank'] = df[stat].rank(ascending=False, method='min')

        if stat == 'FG%':
            rankings['FGM/FGA'] = df['FGM/FGA']
        elif stat == 'FT%':
            rankings['FTM/FTA'] = df['FTM/FTA']

    rankings['TO'] = df['TO']
    rankings[f'TO_rank'] = df['TO'].rank(ascending=True, method='min')

    # Add average rank column
    stat_cols = [col for col in rankings.columns if '_rank' in col]
    rankings['Avg_Rank'] = rankings[stat_cols].mean(axis=1).round(2)

    column_to_move = rankings.pop('Avg_Rank')

    # Then, insert the column at the desired position (e.g., index 1)
    rankings.insert(1, 'Avg_Rank', column_to_move)

    # Sort by average rank (ascending - lower is better)
    rankings = rankings.sort_values('Avg_Rank').reset_index(drop=True)

    #print(rankings)
    return rankings

def teams_to_dataframe(teams):
    """
    Convert teams data to a pandas DataFrame

    Args:
        teams: List of team dicts with 'name' and 'stats'

    Returns:
        pandas DataFrame with team stats as columns
    """
    STAT_MAP = {
        '9004003': 'FGM/FGA',
        '5': 'FG%',
        '9007006': 'FTM/FTA',
        '8': 'FT%',
        '10': '3PTM',
        '12': 'PTS',
        '15': 'REB',
        '16': 'AST',
        '17': 'ST',
        '18': 'BLK',
        '19': 'TO'
    }

    teams_data = []
    for team in teams:
        team_stats = {'name': team['name']}
        for stat_obj in team['stats']:
            stat_id = stat_obj['stat']['stat_id']
            stat_value = str(stat_obj['stat']['value'])

            # Convert to numeric if possible
            if stat_value is None or 'None' in stat_value or not stat_value.strip():
                stat_value = 0
            elif '/' not in stat_value and '.' in stat_value:
                stat_value = float(stat_value)
            elif '/' not in stat_value:
                stat_value = int(stat_value)

            team_stats[STAT_MAP.get(stat_id, stat_id)] = stat_value

        teams_data.append(team_stats)

    return pd.DataFrame(teams_data)

if __name__ == '__main__':
    app.run(
    #    debug=True,
        port=8080
    )
