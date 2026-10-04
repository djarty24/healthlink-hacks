import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
import joblib

print("🛠️ Generating Delta-Based Clinical Data...")
np.random.seed(42)

# SCENARIO 1: Normal Baseline (Delta is ~0 to 1 degrees)
n1 = 3000
delta1 = np.random.normal(0.5, 0.5, n1) 
accel1 = np.random.choice([9.81, 12.5, 14.0], p=[0.7, 0.2, 0.1], size=n1)
risk1 = np.random.uniform(0, 10, n1)

# SCENARIO 2: False Alarm (Delta is ~5 degrees, but foot is resting)
n2 = 3000
delta2 = np.random.normal(5.0, 1.0, n2) 
accel2 = np.random.normal(9.81, 0.1, n2)
risk2 = np.random.uniform(20, 30, n2)

# SCENARIO 3: True Positive (Delta is ~6 degrees AND active friction)
n3 = 3000
delta3 = np.random.normal(6.0, 1.0, n3) 
accel3 = np.random.normal(14.0, 1.5, n3)
risk3 = np.random.uniform(85, 100, n3)

Temp_Delta = np.concatenate([delta1, delta2, delta3])
Accel_Data = np.concatenate([accel1, accel2, accel3])
Risk_Target = np.concatenate([risk1, risk2, risk3])

df = pd.DataFrame({'Temp_Delta': Temp_Delta, 'Accel_Magnitude': Accel_Data, 'Risk_Score': Risk_Target})

print("🧠 Training AI on Temperature Deltas...")
X = df[['Temp_Delta', 'Accel_Magnitude']]
y = df['Risk_Score']

rf_model = RandomForestRegressor(n_estimators=50, max_depth=5, random_state=42)
rf_model.fit(X, y)

joblib.dump(rf_model, 'ulcer_model.pkl')
print("💾 Success! AI upgraded and saved as 'ulcer_model.pkl'")