from pathlib import Path

import pandas as pd

from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from sklearn.linear_model import LinearRegression
from sklearn.ensemble import (
    RandomForestRegressor,
    GradientBoostingRegressor,
)

from sklearn.metrics import (
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)

from xgboost import XGBRegressor


RANDOM_SEED = 42

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

TRAIN_PATH = DATA_DIR / "train.csv"
VAL_PATH = DATA_DIR / "validation.csv"


FEATURE_COLUMNS = [
    "object_size",
    "in_robot_path",
    "distance_to_path",
    "change_type",
    "zone_type",
]

TARGET_COLUMN = "risk_score"

NUMERIC_FEATURES = [
    "object_size",
    "in_robot_path",
    "distance_to_path",
]

CATEGORICAL_FEATURES = [
    "change_type",
    "zone_type",
]


def load_data():
    train_df = pd.read_csv(TRAIN_PATH)
    val_df = pd.read_csv(VAL_PATH)

    X_train = train_df[FEATURE_COLUMNS]
    y_train = train_df[TARGET_COLUMN]

    X_val = val_df[FEATURE_COLUMNS]
    y_val = val_df[TARGET_COLUMN]

    return (
        X_train,
        y_train,
        X_val,
        y_val,
    )


def create_preprocessor():
    return ColumnTransformer(
        transformers=[
            (
                "numeric",
                "passthrough",
                NUMERIC_FEATURES,
            ),
            (
                "categorical",
                OneHotEncoder(
                    handle_unknown="ignore"
                ),
                CATEGORICAL_FEATURES,
            ),
        ]
    )


def create_models():
    return {
        "Linear Regression": LinearRegression(),

        "Random Forest": RandomForestRegressor(
            n_estimators=200,
            random_state=RANDOM_SEED,
            n_jobs=-1,
        ),

        "Gradient Boosting": GradientBoostingRegressor(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=3,
            random_state=RANDOM_SEED,
        ),

        "XGBoost": XGBRegressor(
            n_estimators=200,
            learning_rate=0.05,
            max_depth=3,
            subsample=0.9,
            colsample_bytree=0.9,
            objective="reg:squarederror",
            random_state=RANDOM_SEED,
            n_jobs=-1,
        ),
    }


def evaluate_model(
    name,
    model,
    X_train,
    y_train,
    X_val,
    y_val,
):
    pipeline = Pipeline(
        steps=[
            (
                "preprocessor",
                create_preprocessor(),
            ),
            (
                "model",
                model,
            ),
        ]
    )

    pipeline.fit(
        X_train,
        y_train,
    )

    predictions = pipeline.predict(
        X_val
    )

    mae = mean_absolute_error(
        y_val,
        predictions,
    )

    mse = mean_squared_error(
        y_val,
        predictions,
    )

    rmse = mse ** 0.5

    r2 = r2_score(
        y_val,
        predictions,
    )

    print(f"\n{name}")
    print("-" * 40)
    print(f"MAE  : {mae:.4f}")
    print(f"RMSE : {rmse:.4f}")
    print(f"R²   : {r2:.4f}")

    return {
        "model": name,
        "MAE": mae,
        "RMSE": rmse,
        "R2": r2,
    }


def main():
    (
        X_train,
        y_train,
        X_val,
        y_val,
    ) = load_data()

    print(
        f"Train samples: {len(X_train)}"
    )
    print(
        f"Validation samples: {len(X_val)}"
    )

    models = create_models()

    results = []

    for name, model in models.items():
        result = evaluate_model(
            name,
            model,
            X_train,
            y_train,
            X_val,
            y_val,
        )

        results.append(result)

    results_df = pd.DataFrame(results)

    results_df = results_df.sort_values(
        by="MAE"
    ).reset_index(drop=True)

    print("\n")
    print("=" * 55)
    print("MODEL COMPARISON")
    print("=" * 55)

    print(
        results_df.to_string(
            index=False
        )
    )


if __name__ == "__main__":
    main()