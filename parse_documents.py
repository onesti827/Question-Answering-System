import json

# Load the data (containing about 21,403 documents)
with open('megarhyme-wikinews.json', 'r') as f:
    data = json.load(f)

# Take the first 30 documents
selected_articles = data[:30]

# Save them to a new file
with open('.\\dataset\\my_wikinews_subset.json', 'w') as f:
    json.dump(selected_articles, f, indent=2)