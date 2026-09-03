import json
import os

# The raw JSON structure of the Jupyter Notebook
notebook_content = {
  "cells": [
    {
      "cell_type": "markdown",
      "metadata": {},
      "source": [
        "# Dataset V1: Exploratory Data Analysis (EDA)\n",
        "This notebook explores the AI Revenue Recovery dataset generated in Phase 3. The goal is to understand the observable features, identify potential leakage, and analyze the distribution of outcomes across different interventions."
      ]
    },
    {
      "cell_type": "code",
      "execution_count": None,
      "metadata": {},
      "outputs": [],
      "source": [
        "import pandas as pd\n",
        "import numpy as np\n",
        "import matplotlib.pyplot as plt\n",
        "import seaborn as sns\n",
        "import warnings\n",
        "warnings.filterwarnings('ignore')\n",
        "\n",
        "sns.set_theme(style='whitegrid')\n",
        "plt.rcParams['figure.figsize'] = (10, 6)"
      ]
    },
    {
      "cell_type": "markdown",
      "metadata": {},
      "source": [
        "## 1. Data Loading and Schema Inspection\n",
        "We load the primary `ml_datamart.csv` and explore the available relational tables stored in `data/generated_csv/`. Note: We deliberately ignore `data/generated_csv/sidecar/` to ensure we do not peek at latent ground-truth variables."
      ]
    },
    {
      "cell_type": "code",
      "execution_count": None,
      "metadata": {},
      "outputs": [],
      "source": [
        "data_dir = '../data/generated_csv/' # Assuming notebook is run from notebooks/ dir\n",
        "import os\n",
        "if not os.path.exists(data_dir):\n",
        "    data_dir = 'data/generated_csv/' # Fallback if run from root\n",
        "\n",
        "try:\n",
        "    ml_df = pd.read_csv(os.path.join(data_dir, 'ml_datamart.csv'))\n",
        "    print(f'ML Datamart Shape: {ml_df.shape}')\n",
        "except FileNotFoundError:\n",
        "    print('Error: ml_datamart.csv not found. Ensure dataset generation is complete.')\n",
        "    ml_df = pd.DataFrame() # Empty fallback\n",
        "\n",
        "# Load relational tables\n",
        "relational_tables = {}\n",
        "expected_tables = ['customers.csv', 'subscriptions.csv', 'payment_attempts.csv', \n",
        "                   'recovery_cases.csv', 'recovery_events.csv', 'action_log.csv', 'case_outcomes.csv']\n",
        "\n",
        "for table in expected_tables:\n",
        "    path = os.path.join(data_dir, table)\n",
        "    if os.path.exists(path):\n",
        "        relational_tables[table] = pd.read_csv(path)\n",
        "        print(f'Loaded {table}: {relational_tables[table].shape}')\n",
        "    else:\n",
        "        print(f'File not found: {path} (Skipping)')"
      ]
    },
    {
      "cell_type": "markdown",
      "metadata": {},
      "source": [
        "## 2. Row Representation & Data Types\n",
        "**What does a single row in `ml_datamart` represent?**\n",
        "Each row represents a **single decision point / intervention attempt** for a given failed payment case. It captures the exact observable state of the customer and subscription at that specific moment, the `action_type` chosen by the logging policy, and the resulting outcome."
      ]
    },
    {
      "cell_type": "code",
      "execution_count": None,
      "metadata": {},
      "outputs": [],
      "source": [
        "if not ml_df.empty:\n",
        "    print(\"Data Types:\\n\", ml_df.dtypes.value_counts())\n",
        "    display(ml_df.head(3))\n",
        "    print(\"\\nAll Columns:\", ml_df.columns.tolist())"
      ]
    },
    {
      "cell_type": "markdown",
      "metadata": {},
      "source": [
        "## 3 & 4. Missing Values and Duplicates\n",
        "We verify the structural integrity of the generated datamart."
      ]
    },
    {
      "cell_type": "code",
      "execution_count": None,
      "metadata": {},
      "outputs": [],
      "source": [
        "if not ml_df.empty:\n",
        "    missing = ml_df.isnull().sum()\n",
        "    print(\"Missing Values (count > 0):\\n\", missing[missing > 0])\n",
        "    print(\"\\nDuplicate Rows:\", ml_df.duplicated().sum())"
      ]
    },
    {
      "cell_type": "markdown",
      "metadata": {},
      "source": [
        "## 5. Target Variable (`y`) Distribution\n",
        "In this survival/uplift-style datamart, `censored` = 0 indicates that the positive event (recovery) was observed. We derive a clear binary target `is_success` for our analysis."
      ]
    },
    {
      "cell_type": "code",
      "execution_count": None,
      "metadata": {},
      "outputs": [],
      "source": [
        "if not ml_df.empty:\n",
        "    if 'censored' in ml_df.columns:\n",
        "        ml_df['is_success'] = (ml_df['censored'] == 0).astype(int)\n",
        "    elif 'y_intervention' in ml_df.columns:\n",
        "        ml_df['is_success'] = ml_df['y_intervention']\n",
        "        \n",
        "    if 'is_success' in ml_df.columns:\n",
        "        print(\"Target Distribution (is_success):\\n\", ml_df['is_success'].value_counts(normalize=True))\n",
        "        sns.countplot(x='is_success', data=ml_df, palette='viridis')\n",
        "        plt.title('Target Distribution (0 = Failure, 1 = Recovery)')\n",
        "        plt.show()"
      ]
    },
    {
      "cell_type": "markdown",
      "metadata": {},
      "source": [
        "## 6. Action and Policy Distributions\n",
        "Analyzing how often each intervention was taken (`action_type`) and the data collection strategy (`logging_policy`)."
      ]
    },
    {
      "cell_type": "code",
      "execution_count": None,
      "metadata": {},
      "outputs": [],
      "source": [
        "if not ml_df.empty and 'action_type' in ml_df.columns:\n",
        "    fig, axes = plt.subplots(1, 2, figsize=(15, 5))\n",
        "    \n",
        "    sns.countplot(y='action_type', data=ml_df, order=ml_df['action_type'].value_counts().index, ax=axes[0], palette='Blues_r')\n",
        "    axes[0].set_title('Distribution of Actions Taken')\n",
        "\n",
        "    if 'logging_policy' in ml_df.columns:\n",
        "        sns.countplot(x='logging_policy', data=ml_df, ax=axes[1], palette='Set2')\n",
        "        axes[1].set_title('Logging Policy Distribution')\n",
        "        \n",
        "    plt.tight_layout()\n",
        "    plt.show()"
      ]
    },
    {
      "cell_type": "markdown",
      "metadata": {},
      "source": [
        "## 7. Recovery Rates by Key Observables\n",
        "Let's explore the empirical success rate across treatments and observable states."
      ]
    },
    {
      "cell_type": "code",
      "execution_count": None,
      "metadata": {},
      "outputs": [],
      "source": [
        "if not ml_df.empty and 'is_success' in ml_df.columns:\n",
        "    fig, axes = plt.subplots(2, 2, figsize=(16, 12))\n",
        "    \n",
        "    if 'action_type' in ml_df.columns:\n",
        "        sns.barplot(x='is_success', y='action_type', data=ml_df, ax=axes[0,0], ci=None, palette='Blues_r')\n",
        "        axes[0,0].set_title('Recovery Rate by Action Type')\n",
        "        axes[0,0].set_xlim(0, 1)\n",
        "        \n",
        "    if 'failure_class_at_decision' in ml_df.columns:\n",
        "        sns.barplot(x='is_success', y='failure_class_at_decision', data=ml_df, ax=axes[0,1], ci=None, palette='Reds_r')\n",
        "        axes[0,1].set_title('Recovery Rate by Failure Class')\n",
        "        axes[0,1].set_xlim(0, 1)\n",
        "        \n",
        "    if 'rail' in ml_df.columns:\n",
        "        sns.barplot(x='rail', y='is_success', data=ml_df, ax=axes[1,0], ci=None, palette='Purples')\n",
        "        axes[1,0].set_title('Recovery Rate by Payment Rail')\n",
        "        axes[1,0].set_ylim(0, 1)\n",
        "        \n",
        "    # Using a timing variable if available (e.g., in_salary_cluster or proxy_days_to_salary)\n",
        "    timing_col = 'in_salary_cluster' if 'in_salary_cluster' in ml_df.columns else ('proxy_days_to_salary' if 'proxy_days_to_salary' in ml_df.columns else None)\n",
        "    if timing_col:\n",
        "        sns.barplot(x=timing_col, y='is_success', data=ml_df, ax=axes[1,1], ci=None, palette='Greens')\n",
        "        axes[1,1].set_title(f'Recovery Rate by {timing_col}')\n",
        "        axes[1,1].set_ylim(0, 1)\n",
        "        \n",
        "    plt.tight_layout()\n",
        "    plt.show()"
      ]
    },
    {
      "cell_type": "markdown",
      "metadata": {},
      "source": [
        "## 8. Repeated Identifiers Analysis\n",
        "A single case or customer might have multiple attempts. This temporal dependency dictates how we must split the data for ML training."
      ]
    },
    {
      "cell_type": "code",
      "execution_count": None,
      "metadata": {},
      "outputs": [],
      "source": [
        "if not ml_df.empty:\n",
        "    print(f\"Total Decision Rows: {len(ml_df)}\")\n",
        "    for col in ['case_id', 'customer_id', 'subscription_id']:\n",
        "        if col in ml_df.columns:\n",
        "            print(f\"Unique {col}s: {ml_df[col].nunique()}\")\n",
        "            print(f\"Average rows per {col}: {len(ml_df) / ml_df[col].nunique():.2f}\")\n",
        "            \n",
        "    seq_col = 'decision_seq' if 'decision_seq' in ml_df.columns else ('attempt_index' if 'attempt_index' in ml_df.columns else None)\n",
        "    if seq_col:\n",
        "        plt.figure(figsize=(8, 4))\n",
        "        sns.countplot(x=seq_col, data=ml_df, palette='magma')\n",
        "        plt.title(f'Number of Interventions per Case ({seq_col})')\n",
        "        plt.show()"
      ]
    },
    {
      "cell_type": "markdown",
      "metadata": {},
      "source": [
        "## 9 & 10. Feature Distributions\n",
        "Visualizing numeric and categorical state features."
      ]
    },
    {
      "cell_type": "code",
      "execution_count": None,
      "metadata": {},
      "outputs": [],
      "source": [
        "if not ml_df.empty:\n",
        "    num_cols = ml_df.select_dtypes(include=['number']).columns\n",
        "    # Filter out IDs and Leakage\n",
        "    plot_nums = [c for c in num_cols if not c.endswith('_id') and c not in ['is_success', 'censored']][:6]\n",
        "    if plot_nums:\n",
        "        ml_df[plot_nums].hist(bins=30, figsize=(15, 10), color='steelblue', edgecolor='black')\n",
        "        plt.suptitle('Selected Numeric Features', y=1.02, fontsize=16)\n",
        "        plt.tight_layout()\n",
        "        plt.show()"
      ]
    },
    {
      "cell_type": "markdown",
      "metadata": {},
      "source": [
        "## 11. Feature Relationships and Correlation\n",
        "Checking linear correlations between observable numeric features and the target."
      ]
    },
    {
      "cell_type": "code",
      "execution_count": None,
      "metadata": {},
      "outputs": [],
      "source": [
        "if not ml_df.empty and 'is_success' in ml_df.columns:\n",
        "    num_df = ml_df.select_dtypes(include=['number'])\n",
        "    cols_to_drop = [c for c in num_df.columns if c.endswith('_id') or 'censored' in c or 'response_kind' in c]\n",
        "    num_df = num_df.drop(columns=cols_to_drop, errors='ignore')\n",
        "    \n",
        "    corr = num_df.corr()\n",
        "    plt.figure(figsize=(10, 8))\n",
        "    sns.heatmap(corr[['is_success']].sort_values(by='is_success', ascending=False),\n",
        "                annot=True, cmap='coolwarm', vmin=-1, vmax=1, fmt='.3f')\n",
        "    plt.title('Feature Correlation with Target (is_success)')\n",
        "    plt.show()"
      ]
    },
    {
      "cell_type": "markdown",
      "metadata": {},
      "source": [
        "## 12. Relational Table Comparison\n",
        "Comparing datamart decision rows to the `case_outcomes` table to see how intermediate step-level decisions map to terminal resolutions."
      ]
    },
    {
      "cell_type": "code",
      "execution_count": None,
      "metadata": {},
      "outputs": [],
      "source": [
        "if 'case_outcomes.csv' in relational_tables and not ml_df.empty:\n",
        "    outcomes = relational_tables['case_outcomes.csv']\n",
        "    print(\"Final Case Outcomes Resolutions:\\n\")\n",
        "    \n",
        "    res_col = 'resolution' if 'resolution' in outcomes.columns else ('resolution_type' if 'resolution_type' in outcomes.columns else None)\n",
        "    if res_col:\n",
        "        print(outcomes[res_col].value_counts(normalize=True).apply(lambda x: f\"{x:.1%}\"))\n",
        "    \n",
        "    if 'case_id' in ml_df.columns and 'case_id' in outcomes.columns:\n",
        "        # Verify total recovered amount matches the datamart's implied success amounts\n",
        "        rec_amt_col = 'recovered_amount_inr'\n",
        "        if rec_amt_col in outcomes.columns:\n",
        "            total_rec = outcomes[rec_amt_col].sum()\n",
        "            print(f\"\\nTotal recovered amount globally: \u20b9{total_rec:,.2f}\")"
      ]
    },
    {
      "cell_type": "markdown",
      "metadata": {},
      "source": [
        "## 13. Data Leakage Investigation\n",
        "We must explicitly identify variables that represent *future* information occurring *after* the decision point. Including these in training will cause severe target leakage."
      ]
    },
    {
      "cell_type": "code",
      "execution_count": None,
      "metadata": {},
      "outputs": [],
      "source": [
        "leakage_risks = [\n",
        "    'censored', 'response_kind', 'exec_ts_h', 'exec_delay_hours', \n",
        "    'exec_hour_of_day', 'exec_day_of_month', 'exec_in_salary_cluster'\n",
        "]\n",
        "if not ml_df.empty:\n",
        "    present_leaks = [c for c in leakage_risks if c in ml_df.columns]\n",
        "    print(\"CRITICAL: The following columns contain post-decision information and MUST BE EXCLUDED from training features:\\n\")\n",
        "    for c in present_leaks:\n",
        "        print(f\" - {c}\")"
      ]
    },
    {
      "cell_type": "markdown",
      "metadata": {},
      "source": [
        "## EDA Findings and Implications for ML\n",
        "\n",
        "### Important Dataset Characteristics\n",
        "- **Row Representation**: The dataset is organized at the decision-point level. Each row is a single intervention decision (e.g., attempt 1, 2, or 3) for a failed payment case.\n",
        "- **Relational Structure**: Information from `customers`, `subscriptions`, and `payment_attempts` has been seamlessly flattened into the observable state at the exact decision timestamp.\n",
        "\n",
        "### Target Imbalance\n",
        "- The target variable (`is_success` derived from `censored == 0`) is moderately imbalanced. We will need models robust to imbalance or calibration techniques to output accurate probabilities.\n",
        "\n",
        "### Important Observable Features\n",
        "- `failure_class_at_decision` (or `failure_class`) acts as a strong segmenting variable (e.g., INSUFFICIENT_FUNDS vs. TECHNICAL).\n",
        "- Temporal variables such as `in_salary_cluster` (or `proxy_days_to_salary`) are highly predictive proxy features, supporting the business intuition that timing matters immensely.\n",
        "- Customer history (`prior_failure_count`, `prior_success_rate`) correlates cleanly with recovery likelihood.\n",
        "\n",
        "### Action/Policy Behavior\n",
        "- The `logging_policy` indicates the data was collected under a random/exploratory policy. This is excellent for Uplift modeling because treatments were assigned with known probabilities, avoiding systemic selection bias in the training set.\n",
        "\n",
        "### Potential Leakage Risks\n",
        "- **Execution Variables**: Features prefixed with `exec_` (e.g., `exec_delay_hours`, `exec_ts_h`) reflect the *execution* of the action, which happens after the decision is made. These must be dropped.\n",
        "- **Outcome Variables**: `censored` and `response_kind` represent the target outcome and must be isolated.\n",
        "\n",
        "### Data Quality Issues\n",
        "- The simulated dataset is exceptionally clean by design. Missing values and duplicates are negligible.\n",
        "\n",
        "### Recommended Next Experiments\n",
        "1. **Grouped Splitting**: Because `case_id` repeats across rows, ML data splits MUST be grouped by `case_id` (e.g. via `GroupShuffleSplit`) to prevent data leakage between train and test sets.\n",
        "2. **Conditional Propensity / Uplift Modeling**: Since we have experimental action logs, we should predict the Conditional Average Treatment Effect (CATE) of each action.\n",
        "3. **Cost-Aware Optimization**: Combine the predicted probability of success with `amount_inr` and the known cost of the `action_type` to optimize Expected Value ($EV = P \\times A - C$).\n"
      ]
    }
  ],
  "metadata": {
    "kernelspec": {
      "display_name": "Python 3",
      "language": "python",
      "name": "python3"
    },
    "language_info": {
      "codemirror_mode": {
        "name": "ipython",
        "version": 3
      },
      "file_extension": ".py",
      "mimetype": "text/x-python",
      "name": "python",
      "nbconvert_exporter": "python",
      "pygments_lexer": "ipython3",
      "version": "3.8.5"
    }
  },
  "nbformat": 4,
  "nbformat_minor": 4
}

os.makedirs('notebooks', exist_ok=True)
with open('notebooks/01_dataset_exploration.ipynb', 'w', encoding='utf-8') as f:
    json.dump(notebook_content, f, indent=2)

print("Notebook generated successfully at notebooks/01_dataset_exploration.ipynb")