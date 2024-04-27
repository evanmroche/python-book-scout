import requests
import datetime
import pytz
import csv

API_KEY = "YOUR API KEY HERE" # Get a free api key from theoddsapi.com
SPORT_KEY = 'upcoming' # Can be changed, check theoddsapi.com for documentation


# Define printMenu() function
def printMenu():
    print("""
                  ____        __  __                       
                 / __ \__  __/ /_/ /_  ____  ____          
                / /_/ / / / / __/ __ \/ __ \/ __ \         
               / ____/ /_/ / /_/ / / / /_/ / / / /         
              /_/    \__, /\__/_/ /_/\____/_/ /_/          
    ____            /____/    _____                  __    
   / __ )____  ____  / /__   / ___/_________  __  __/ /_   
  / __  / __ \/ __ \/ //_/   \__ \/ ___/ __ \/ / / / __/   
 / /_/ / /_/ / /_/ / ,<     ___/ / /__/ /_/ / /_/ / /_     
/_____/\____/\____/_/|_|   /____/\___/\____/\__,_/\__/       

By: Evan Roche
Using: TheOddsApi                                                            
""")
# Call printMenu() function
printMenu()



def decimal_to_american(decimal_odds):
    if decimal_odds == 1.0:
        # In betting, odds of 1.0 might not be practical and could indicate a data issue.
        # We can handle it by returning a neutral American odds value or logging an error.
        # Here, I choose to return 0, which typically isn't valid but will avoid crashes.
        return 0
    elif decimal_odds >= 2.0:
        return int((decimal_odds - 1) * 100)
    else:
        return int(-100 / (decimal_odds - 1))

def load_bookmakers_from_file(file_path):
    try:
        with open(file_path, mode='r') as file:
            csv_reader = csv.reader(file)
            bookmakers = {row[0] for row in csv_reader}
        return bookmakers
    except Exception as e:
        print(f"Failed to load bookmakers from file: {e}")
        return set()

def get_user_bookmakers(bookmakers_available):
    print("1. Choose from available bookmakers.")
    print("2. Load bookmakers from a file.")
    choice = input("Select an option (1 or 2): ")
    if choice == '1':
        print("Available bookmakers:")
        for idx, bookmaker in enumerate(bookmakers_available, start=1):
            print(f"{idx}. {bookmaker}")
        selected_indexes = input("Enter the numbers of the bookmakers you want to use (comma-separated): ")
        selected_bookmakers = {bookmakers_available[int(i) - 1] for i in selected_indexes.split(',')}
    elif choice == '2':
        file_path = input("Enter the file path: ")
        selected_bookmakers = load_bookmakers_from_file(file_path)
    else:
        print("Invalid choice, defaulting to available bookmakers.")
        selected_bookmakers = bookmakers_available
    return selected_bookmakers

def parse_utc_time(utc_string):
    utc_time = datetime.datetime.strptime(utc_string, "%Y-%m-%dT%H:%M:%SZ")
    utc_zone = pytz.utc
    denver_zone = pytz.timezone('America/Denver')
    denver_time = utc_zone.localize(utc_time).astimezone(denver_zone)
    return denver_time

def format_time_difference(event_time):
    now = datetime.datetime.now(pytz.timezone('America/Denver'))
    if event_time > now:
        diff = event_time - now
        return f"T- {diff}"
    else:
        diff = now - event_time
        return f"T+ {diff}"

def find_best_odds(data, selected_bookmakers):
    best_odds = {}
    for game in data:
        game_id = game['id']
        league = game['sport_title']
        teams = f"{game['home_team']} vs {game['away_team']}"
        game_time = parse_utc_time(game['commence_time'])
        formatted_game_time = format_time_difference(game_time)
        best_odds[game_id] = {'league_teams': league + ': ' + teams, 'commence_time': formatted_game_time, 'markets': {}}
        for bookmaker in game['bookmakers']:
            if bookmaker['key'] not in selected_bookmakers:
                continue
            last_update_time = parse_utc_time(bookmaker['last_update'])
            formatted_last_update = format_time_difference(last_update_time)
            for market in bookmaker['markets']:
                market_key = market['key']
                if market_key not in best_odds[game_id]['markets']:
                    best_odds[game_id]['markets'][market_key] = {}
                for outcome in market['outcomes']:
                    outcome_name = outcome['name']
                    point = outcome.get('point', '')
                    if 'Over' in outcome_name or 'Under' in outcome_name:
                        outcome_name += f" {point} Points"
                    outcome_price = outcome['price']
                    if outcome_name not in best_odds[game_id]['markets'][market_key] or \
                       outcome_price > best_odds[game_id]['markets'][market_key][outcome_name]['price']:
                        best_odds[game_id]['markets'][market_key][outcome_name] = {
                            'bookmaker': bookmaker['key'],
                            'price': outcome_price,
                            'american_odds': decimal_to_american(outcome_price),
                            'last_update': formatted_last_update
                        }
    return best_odds

def calculate_bets(arbitrage_opportunity):
    total_inv_price = arbitrage_opportunity['total_inv_price']
    required_total = 100 / total_inv_price  # Example total amount to bet, can be adjusted
    bets = {}
    for outcome, details in arbitrage_opportunity['outcomes'].items():
        bet_amount = required_total / details['price']
        bets[outcome] = {
            'bet_amount': bet_amount,
            'bookmaker': details['bookmaker'],
            'price': details['price'],
            'american_odds': details['american_odds'],
            'last_update': details['last_update']
        }
    return bets

def find_arbitrage_opportunities(best_odds):
    arbitrage_opportunities = []
    for game_id, game_data in best_odds.items():
        for market_key, outcomes in game_data['markets'].items():
            total_inv_price = sum(1 / outcome['price'] for outcome in outcomes.values())
            if total_inv_price < 1:
                arbitrage_opportunities.append({
                    'league_teams': game_data['league_teams'],
                    'commence_time': game_data['commence_time'],
                    'market': market_key,
                    'total_inv_price': total_inv_price,
                    'outcomes': outcomes
                })
    # Sort opportunities by total inverse price in ascending order
    arbitrage_opportunities.sort(key=lambda x: x['total_inv_price'])
    return arbitrage_opportunities

def main():
    data = requests.get(
        f'https://api.the-odds-api.com//v4/sports/{SPORT_KEY}/odds/?apiKey={API_KEY}&regions=us,us2&markets=h2h,totals',
        ).json()

    bookmakers_available = {bk['key'] for game in data for bk in game['bookmakers']}
    # selected_bookmakers = get_user_bookmakers(list(bookmakers_available))
    selected_bookmakers = ['fanduel','draftkings','betmgm','williamhill_us']

    best_odds = find_best_odds(data, selected_bookmakers)
    opportunities = find_arbitrage_opportunities(best_odds)

    print("\nArbitrage Opportunities:")
    
    for opp in opportunities:
        print(f"\n{opp['league_teams']} starting {opp['commence_time']}, Market: {opp['market']}, Total Inverse Price: {opp['total_inv_price']:.4f}")
        bets = calculate_bets(opp)
        for outcome, details in bets.items():
            print(f"  {details['bookmaker']} - {opp['league_teams']} (last update {details['last_update']}):\n    Bet on {outcome}:\n    Bet: ${details['bet_amount']:.2f}, Decimal Odds: {details['price']}, American Odds: {details['american_odds']}")

if __name__ == "__main__":
    main()
