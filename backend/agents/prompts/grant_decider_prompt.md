# Grant Decider Prompt

Use this prompt + model configuration for the `grant_decider` LLM column inside the `scrap_result` Action Table. It inspects upstream scraping/verifier/corrector outputs and decides whether the record can be synced into the `grants` knowledge table.

---

## Prompt Template

```
Table name: "scrap_result"

grant_scrap: ${grant_scrap}
grant_verified: ${grant_verified}
grant_final: ${grant_final}

Based on the available information, provide an appropriate response for the column "grant_decider".

Rules:
1. If `grant_final` already contains a verified JSON object that follows the structure
   {grantName, period, grantDescription, applicationProcess, requiredDocuments},
   respond with the exact text: proceed to knowledge table sync
2. If `grant_final` equals the string "failed to verify" (case-insensitive) or is missing required fields,
   respond with a short factual explanation quoting the problematic field(s). Example:
   "failed because period range is missing in grant_final" or
   "failed because source mismatch between grant_verified and grant_final".
3. Use only the evidence provided in grant_scrap, grant_verified, and grant_final.
4. Do not hallucinate, add pleasantries, or include markdown. Return a single sentence.
5. Remember that you act as a single spreadsheet cell; stay concise.
```

---

## Model Configuration

- Model ID: `ellm/qwen/qwen3-30b-a3b-2507`
- Temperature: `0.0`
- Max Tokens: `200`
- Top-p: `0.1`

These conservative settings keep the output deterministic and prevent the column from introducing unsupported claims.

