# NBA Data Analytics & Predictive Modeling

## Overview
This project focuses on leveraging data-driven analytics to identify high-probability outcomes for daily NBA investments. By synthesizing real-time player statistics and team trends, this model aims to remove emotional bias from the decision-making process.

## The 12-Filter Logic Engine
The core of this project is a proprietary 12-filter system used to evaluate player performance. Each data point must pass a series of boolean checks before being flagged as a "High-Confidence" investment.

### The Data Pipeline (ELT)
1. **Extraction:** Daily querying of Statmuse to pull historical player splits.
2. **Transformation:** Parsing volume (Usage/Minutes) into a weighted score:
   $$\text{Investment Score} = \sum_{i=1}^{12} (Filter_i \times Weight_i)$$
3. **Validation:** Cross-referencing modeled outcomes against Outlier market trends to identify "edge."

## Tech & Data Stack
* **Primary Tools:** Statmuse (Historical data), Outlier (Market trend analysis).
* **Logic:** Developed using logical operators and conditional statistical filtering.
* **Documentation:** Managed via VS Code.

##  Disclaimer
This repository is for data analysis and educational purposes only. It showcases the application of MIS data filtering techniques to sports-related datasets.
