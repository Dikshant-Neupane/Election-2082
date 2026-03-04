import pandas as pd
from math import ceil

# Load files
results = pd.read_csv('data/election_results_2082.csv')
parties = pd.read_csv('data/political_parties_2082.csv')

# Winners per constituency
winners = results[results['rank_in_constituency'] == 1].copy()
# merge party info
winners = winners.merge(parties[['party_id','party_abbreviation','party_leader_name']], on='party_id', how='left')

# Seat counts
seat_counts = winners['party_abbreviation'].value_counts()
total_seats = int(seat_counts.sum())
if total_seats == 0:
    raise SystemExit('No winners found (total_seats == 0)')

top_party = seat_counts.idxmax()
top_seats = int(seat_counts.max())
seat_pct = 100 * top_seats / total_seats
majority_threshold = ceil(total_seats / 2)
has_majority = top_seats >= majority_threshold

# leader name
leader_row = parties[parties['party_abbreviation'] == top_party]
leader_name = leader_row['party_leader_name'].iloc[0] if not leader_row.empty else ''

# Prepare markdown summary
md = []
md.append('### Election Outcome')
md.append('')
md.append(f'- **Winning party:** {top_party} ({top_seats} / {total_seats} seats, {seat_pct:.1f}%)')
md.append(f'- **Party leader:** {leader_name or "(unknown)"}')
md.append(f'- **Majority:** {"Yes" if has_majority else "No"} (majority threshold = {majority_threshold} seats)')
md.append('')
md.append('> Note: This project uses synthetic data for educational purposes; do not treat results as factual.')
md.append('')

with open('winner_summary.md','w', encoding='utf-8') as f:
    f.write('\n'.join(md))

print('\n'.join(md))
print('\nSaved winner_summary.md')
