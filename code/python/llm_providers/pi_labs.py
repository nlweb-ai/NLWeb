import asyncio
import json

import time
import withpi 
import os


pi_client = None

async def pi_score_item(query, answer):
    global pi_client
    if (not pi_client):
        api_key = os.environ.get("PI_LABS_KEY")
        pi_client = withpi.PiClient(api_key=api_key)
    start_time = time.time()
    scoringSystemMetrics = pi_client.scoring_system.score(
        llm_input=query,
        llm_output=answer,
        scoring_spec=[
            {'question': 'Is this response relevant?'},
            {'question': 'Is this response helpful?'}
        ]
    )
    time_taken = round(time.time() - start_time, 2)
    score = scoringSystemMetrics.total_score * 100
    return score, time_taken


async def pi_scoring_comparison(file):
    # Generate output filename
    base_name = file.rsplit('.', 1)[0] if '.' in file else file
    output_file = f"{base_name}_pi_eval.csv"

    with open(file, 'r') as f:
        lines = f.readlines()
        data = []
        for line in lines:
            try:
                data.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        for item in data:
            item_fields = {
                "url": item.get("url", ""),
                "name": item.get("name", ""),
                "site": item.get("site", ""),
                "siteUrl": item.get("site", ""),
                "score": item.get("ranking", {}).get("score", 0),
                "description": item.get("ranking", {}).get("description", ""),
                "schema_object": item.get("schema_object", {}),
                "query": item.get("query", "")
            }
            desc = json.dumps(item_fields["schema_object"])
            pi_score, time_taken = await pi_score_item(item['query'], desc)
            
            item['ranking']['score'] = pi_score
            csv_line = f"O={item_fields['score']},P={pi_score},T={time_taken},Q={item_fields['query']},N={item_fields['name']}" #,D={item_fields['description']}"
            if (item_fields['score'] > 64 or pi_score > 30):
              print(csv_line) 
            with open(output_file, 'a') as f:
                f.write(csv_line + '\n')
            
       

     

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m llm_providers.pi_labs <input_file.jsonl>")
        sys.exit(1)

    input_file = sys.argv[1]
    asyncio.run(pi_scoring_comparison(input_file))