"""
Export key charts from the Election-2082 dataset into `images/`.
Run this script from the repository root after creating/activating the virtualenv.

Example:
    .venv\Scripts\activate
    python scripts/export_images.py

This script uses a non-interactive backend so it works on headless CI.
"""

import os
import warnings
warnings.filterwarnings("ignore")

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import LabelEncoder

DATA = os.path.join(os.path.dirname(__file__), '..', 'data')
IMAGES = os.path.join(os.path.dirname(__file__), '..', 'images')
os.makedirs(IMAGES, exist_ok=True)

def load_tables():
    read = lambda name: pd.read_csv(os.path.join(DATA, name))
    return {
        'parties': read('political_parties_2082.csv'),
        'candidates': read('candidates_2082.csv'),
        'voters': read('voters_2082.csv'),
        'votes': read('votes_2082.csv'),
        'results': read('election_results_2082.csv'),
        'events': read('campaign_events.csv'),
        'social': read('social_media_trends.csv'),
        'news': read('media_news_coverage.csv'),
        'scandals': read('political_scandals.csv'),
    }


def plot_parliament(results_df, parties_df, out_path):
    winners = results_df[results_df['rank_in_constituency'] == 1].copy()
    winners = winners.merge(parties_df[['party_id', 'party_abbreviation']], on='party_id', how='left')
    winners['party_abbreviation'] = winners['party_abbreviation'].fillna('IND')
    seat_dist = winners['party_abbreviation'].value_counts().sort_values(ascending=False)

    fig, ax = plt.subplots(1, 2, figsize=(12, 5))
    seat_dist.plot(kind='barh', ax=ax[0], color=sns.color_palette('tab10', len(seat_dist)))
    ax[0].invert_yaxis()
    ax[0].set_xlabel('Seats Won')
    ax[0].set_title('Seats Won by Party')

    ax[1].pie(seat_dist.values, labels=seat_dist.index, autopct='%1.0f%%', startangle=90)
    ax[1].set_title('Parliament Composition')

    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close()


def plot_winner_vote_pct(results_df, out_path):
    winners = results_df[results_df['rank_in_constituency'] == 1].copy()
    winners = winners.sort_values('constituency_id')
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.bar(winners['constituency_id'].astype(str), winners['vote_percentage'], color='steelblue')
    ax.set_xlabel('Constituency')
    ax.set_ylabel('Winner Vote %')
    ax.set_title("Winner Vote Percentage by Constituency")
    ax.tick_params(axis='x', rotation=90, labelsize=6)
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close()


def plot_feature_importance(candidates_df, events_df, social_df, news_df, scandals_df, results_df, out_path):
    # Build a reduced master similar to the notebook but compact
    master = candidates_df[['candidate_id', 'age', 'gender', 'education_level', 'declared_assets_npr', 'campaign_budget_npr', 'criminal_case_status', 'previous_election_experience']].copy()

    # campaign agg
    camp_agg = events_df.groupby('candidate_id').agg(total_events=('event_id', 'count'), total_attendance=('attendance_estimate', 'sum'))
    master = master.merge(camp_agg, on='candidate_id', how='left')
    master[['total_events', 'total_attendance']] = master[['total_events', 'total_attendance']].fillna(0)

    # social agg
    soc_agg = social_df.groupby('related_candidate_id').agg(avg_social_sentiment=('sentiment_score', 'mean'), total_mentions=('mentions_count', 'sum')).reset_index().rename(columns={'related_candidate_id':'candidate_id'})
    master = master.merge(soc_agg, on='candidate_id', how='left')
    master[['avg_social_sentiment','total_mentions']] = master[['avg_social_sentiment','total_mentions']].fillna(0)

    # news agg
    news_agg = news_df.groupby('candidate_id').agg(total_news=('news_id','count'), avg_news_impact=('impact_score','mean')).reset_index()
    master = master.merge(news_agg, on='candidate_id', how='left')
    master[['total_news','avg_news_impact']] = master[['total_news','avg_news_impact']].fillna(0)

    # scandal agg
    sc_agg = scandals_df.groupby('candidate_id').agg(num_scandals=('scandal_id','count')).reset_index()
    master = master.merge(sc_agg, on='candidate_id', how='left')
    master['num_scandals'] = master['num_scandals'].fillna(0)

    # target
    master = master.merge(results_df[['candidate_id','vote_percentage']], on='candidate_id')

    # encode simple categoricals
    le_gender = LabelEncoder()
    master['gender_enc'] = le_gender.fit_transform(master['gender'].astype(str))
    le_edu = LabelEncoder()
    master['edu_enc'] = le_edu.fit_transform(master['education_level'].astype(str))
    le_crim = LabelEncoder()
    master['crim_enc'] = le_crim.fit_transform(master['criminal_case_status'].astype(str))

    feature_cols = ['age','gender_enc','edu_enc','declared_assets_npr','campaign_budget_npr','crim_enc','previous_election_experience','total_events','total_attendance','avg_social_sentiment','total_mentions','total_news','avg_news_impact','num_scandals']

    X = master[feature_cols].fillna(0).values
    y = master['vote_percentage'].values

    # small random forest
    rf = RandomForestRegressor(n_estimators=100, max_depth=8, random_state=0)
    rf.fit(X, y)
    importances = pd.Series(rf.feature_importances_, index=feature_cols).sort_values()

    fig, ax = plt.subplots(figsize=(8, 6))
    importances.plot(kind='barh', ax=ax, color='teal')
    ax.set_title('Feature Importance (Random Forest)')
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, bbox_inches='tight')
    plt.close()

    # also save prediction results and an actual vs predicted scatter
    try:
        y_pred = rf.predict(X)
        preds = pd.DataFrame({
            'candidate_id': master['candidate_id'],
            'actual_vote_percentage': y,
            'predicted_vote_percentage': y_pred
        })
        preds.to_csv(os.path.join(IMAGES, 'predictions.csv'), index=False)

        fig, ax = plt.subplots(figsize=(6, 6))
        ax.scatter(y, y_pred, c='steelblue', alpha=0.6, edgecolor='k')
        ax.plot([y.min(), y.max()], [y.min(), y.max()], 'r--', lw=1)
        ax.set_xlabel('Actual Vote %')
        ax.set_ylabel('Predicted Vote %')
        ax.set_title('Actual vs Predicted Vote %')
        plt.tight_layout()
        plt.savefig(os.path.join(IMAGES, 'prediction_scatter.png'), dpi=150, bbox_inches='tight')
        plt.close()
    except Exception:
        pass


if __name__ == '__main__':
    tables = load_tables()
    try:
        plot_parliament(tables['results'], tables['parties'], os.path.join(IMAGES, 'parliament.png'))
        print('Saved images/parliament.png')
    except Exception as e:
        print('Failed to save parliament plot:', e)

    try:
        plot_winner_vote_pct(tables['results'], os.path.join(IMAGES, 'winner_vote_pct.png'))
        print('Saved images/winner_vote_pct.png')
    except Exception as e:
        print('Failed to save winner vote pct plot:', e)

    try:
        plot_feature_importance(tables['candidates'], tables['events'], tables['social'], tables['news'], tables['scandals'], tables['results'], os.path.join(IMAGES, 'feature_importance.png'))
        print('Saved images/feature_importance.png')
    except Exception as e:
        print('Failed to save feature importance plot:', e)

    print('Done.')
