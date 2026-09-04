# Adult Census Income Classification

## 1. Project Objective

This project builds a machine-learning classification system to predict whether an individual's annual income is **greater than $50K** using demographic, employment, education, and financial attributes from the Adult Census Income dataset.

The primary business consideration is **precision**. False positives are treated as more costly than false negatives because incorrectly identifying a person as belonging to the higher-income class can lead to inappropriate targeting, decisions, or resource al

## 2. Dataset

**Dataset:** Adult Census Income  
**Source:** OpenML Adult dataset, loaded using `fetch_openml('adult', version=2, as_frame=True)`

### Target

The target variable represents annual income:

- `<=50K`
- `>50K`

The positive class is `>50K`.

The dataset was divided using a stratified split with `random_state=42`:

| Partition | Samples |
|---|---:|
| Training | 34,188 |
| Development | 4,885 |
| Untouched hold-out test | 9,769 |

The positive-class rate was approximately **23.93%** in each partition.

---

## 3. Data Preparation

The project uses a leak-free preprocessing pipeline.

### Numeric features
- Missing values are handled using median imputation.
- Features are scaled where required by the selected estimator.

### Categorical features
- Missing values are handled using most-frequent imputation.
- Categorical variables are transformed using one-hot encoding.

All preprocessing is fitted only on the appropriate training data through the pipeline, preventing information from the development or hold-out test sets from leaking into model training.

---

## 4. Feature Engineering

Six engineered features were introduced during model development:

1. **Age buckets**
   - `<=25`
   - `26-35`
   - `36-45`
   - `46-55`
   - `56-65`
   - `65+`

2. **Hours-per-week buckets**
   - `<=20`
   - `21-35`
   - `36-40`
   - `41-50`
   - `50+`

3. **Capital-gain indicator**
   - `has_capital_gain = 1` when capital gain is greater than zero, otherwise `0`.

4. **Log-transformed capital gain**
   - `log_capital_gain = log1p(capital-gain)`

5. **Higher-education indicator**
   - `higher_education = 1` when `education-num >= 13`, otherwise `0`.

6. **Education-hours interaction**
   - `edu_hours_interaction = education-num × hours-per-week`

These transformations are incorporated into the model pipeline so that inference does not require manual feature preparation.

---

## 5. Model Development

The project evaluated multiple classification approaches during model development, including:

- Logistic Regression
- Decision Tree
- Random Forest
- Histogram-based Gradient Boosting

Day 3 cross-validation compared the shortlisted approaches using precision as the primary metric. The strongest candidate was the histogram-based gradient boosting approach, which achieved approximately:

- **Precision:** 0.7764 ± 0.0116
- **ROC-AUC:** 0.9259 ± 0.0038
- **F1:** 0.7051 ± 0.0076

Feature selection was also evaluated. Reducing the feature space to the selected subset did not improve precision over the full feature set, so the full feature set was retained.

---

## 6. Hyperparameter Tuning and Calibration

Hyperparameter searches were performed using cross-validation with a precision-focused scoring strategy.

The final saved estimator loaded from the Day 4 artifact is a:

**`CalibratedClassifierCV`**

The final decision threshold selected during development was:

**0.425**

The threshold was selected on development data rather than the untouched hold-out test set. This preserves the role of the hold-out set as an unbiased final evaluation set.

---

## 7. Final Hold-Out Test Performance

The final model was evaluated once on the untouched hold-out test set.

| Metric | Score |
|---|---:|
| Accuracy | 0.859351 |
| Precision | 0.763676 |
| Recall | 0.597092 |
| F1 | 0.670187 |
| ROC-AUC | 0.910646 |
| PR-AUC | 0.793375 |
| Brier Score | 0.099490 |

### Confusion Matrix

| | Predicted <=50K | Predicted >50K |
|---|---:|---:|
| Actual <=50K | 6,999 | 432 |
| Actual >50K | 942 | 1,396 |

Therefore:

- **True Negatives:** 6,999
- **False Positives:** 432
- **False Negatives:** 942
- **True Positives:** 1,396

Precision remained the main decision criterion because false positives carry greater practical cost in the project framing.

---

## 8. Error Analysis

The hold-out evaluation showed that the model makes both false-positive and false-negative errors.

Observed high-confidence patterns included:

- Some older private-sector workers with substantial capital gains were incorrectly classified as belonging to the `>50K` class.
- Several married respondents in managerial or professional occupations were also among the higher-confidence false positives.
- False negatives included younger workers and respondents with `HS-grad` or `Some-college` education and little or no capital gain.

These patterns suggest that income classification depends on interactions among education, occupation, age, work characteristics, and financial variables rather than on a single attribute.

Subgroup analysis was also performed across variables including:

- Sex
- Race
- Education
- Workclass
- Marital status
- Occupation
- Age
- Hours-per-week

Groups with fewer than 30 observations were excluded from subgroup-level analysis to avoid drawing conclusions from extremely small samples.

---

## 9. Feature and Model Interpretation

The final saved estimator is wrapped in `CalibratedClassifierCV`. Because the loaded calibrated estimator does not directly expose a simple `coef_` or `feature_importances_` interface, the final Day 5 notebook did **not fabricate a feature-importance ranking**.

The project therefore treats the error analysis and the engineered-feature behavior as supporting evidence rather than claiming an unsupported exact feature ranking.

The analysis indicates that education, work characteristics, age, capital gain, and their interactions are important dimensions of the income-classification problem.

---

## 10. Production Inference

The trained model is saved as a serialized Joblib artifact.

Inference follows this workflow:

1. Load the saved Joblib artifact.
2. Provide a new input record using the original raw feature structure.
3. Pass the raw input directly into the saved pipeline.
4. The pipeline automatically performs feature engineering and preprocessing.
5. The model produces a probability for the `>50K` class.
6. The probability is compared with the selected threshold of **0.425**.
7. The final class prediction is returned.

No manual preprocessing should be performed before inference.

### Example inference behavior

Using unseen hold-out examples:

| Example | Predicted probability | Prediction |
|---|---:|---|
| 1 | 0.038434 | <=50K |
| 2 | 0.044800 | <=50K |
| 3 | 0.078206 | <=50K |
| 4 | 0.029020 | <=50K |
| 5 | 0.028990 | <=50K |
| 6 | 0.138463 | <=50K |
| 7 | 0.029261 | <=50K |
| 8 | 0.936708 | >50K |
| 9 | 0.247950 | <=50K |
| 10 | 0.788985 | >50K |

The prediction rule is:

`prediction = >50K` when `probability >= 0.425`; otherwise `<=50K`.

---

## 11. Reproduction

The project was developed and executed in Google Colab.

### Environment used

| Package | Version |
|---|---|
| Python | 3.13.15 |
| NumPy | 2.1.3 |
| pandas | 2.2.3 |
| scikit-learn | 1.6.1 |
| joblib | 1.5.3 |
| matplotlib | 3.10.0 |
| SciPy | 1.16.3 |

### Basic reproduction workflow

1. Open the final Day 5 notebook in Google Colab.
2. Install/use the required package versions if necessary.
3. Load the Adult dataset from OpenML.
4. Recreate the stratified train/development/hold-out split with `random_state=42`.
5. Load the saved Day 4 model artifact.
6. Run the Day 5 validation and error-analysis sections.
7. Evaluate the model on the untouched hold-out test set.
8. Run the production-inference example using raw input data.

The saved pipeline contains the feature engineering and preprocessing required for inference.

---

## 12. Project Files

A complete submission should contain:

- `final_model.joblib` or the saved Day 4/Day 5 model artifact
- `Day5_Tasks.ipynb` or the final executed Day 5 notebook
- `README.md`
- Final project report
- Final metrics table
- Confusion matrix
- Learning/calibration visualizations
- Feature/model interpretation output where supported
- Inference examples
- `requirements.txt` or equivalent environment/version information

---

## 13. Limitations

1. The dataset represents a specific census-income prediction setting and may not generalize to modern populations or other regions.
2. The final hold-out evaluation is based on the available Adult Census dataset and does not establish performance on future or independently collected data.
3. Some subgroup analyses can be sensitive to sample size and dataset representation.
4. The calibrated model does not expose a direct feature-importance interface at the outer estimator level, so an exact final feature ranking was not claimed.
5. The selected threshold reflects the project's precision-focused objective and may need to be recalibrated if the relative business costs of false positives and false negatives change.
6. The serialized model depends on compatible Python and library versions for reliable loading and inference.

---

## 14. Future Improvements

Potential next steps include:

- Evaluate the model on a temporally or geographically independent dataset.
- Perform deeper calibration analysis across subgroups.
- Investigate cost-sensitive learning and explicit false-positive cost functions.
- Test additional ensemble models and threshold-selection strategies.
- Perform more detailed fairness and subgroup stability analysis.
- Package inference into a small API or application.
- Add automated model and data validation before deployment.
- Monitor prediction quality and calibration after deployment.

---

## 15. Final Takeaway

The project produced a reproducible, calibrated income-classification pipeline with an explicit precision-focused decision threshold.

On the untouched hold-out test set, the final model achieved **0.763676 precision**, **0.597092 recall**, **0.670187 F1**, **0.910646 ROC-AUC**, and **0.793375 PR-AUC**.

The saved pipeline is designed so that raw inputs can be passed directly to the model without manually repeating feature engineering or preprocessing.
