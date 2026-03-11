import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from giros_bot.schemas.state import AgentState, ArticleFormat, ContentType, FrontendCategory
from giros_bot.graph.nodes.scheduler import CATEGORY_ROTATION, FORMAT_ROTATION

print(f"Number of categories: {len(CATEGORY_ROTATION)}")
print(f"Number of formats: {len(FORMAT_ROTATION)}")

# Verify rotation loop for first 30 days
print("\n--- ROTATION FOR FIRST 10 DAYS ---")
for day in range(1, 11):
    category = CATEGORY_ROTATION[(day - 1) % len(CATEGORY_ROTATION)]
    fmt = FORMAT_ROTATION[(day - 1) % len(FORMAT_ROTATION)]
    print(f"Day {day}: Category = {category.value} | Format = {fmt.value}")

print("\n--- MAGIC DAY 31 ---")
# Previous setup would repeat exactly on day 31. Let's see if it's different now.
day = 31
category = CATEGORY_ROTATION[(day - 1) % len(CATEGORY_ROTATION)]
fmt = FORMAT_ROTATION[(day - 1) % len(FORMAT_ROTATION)]
print(f"Day {day}: Category = {category.value} | Format = {fmt.value}")

