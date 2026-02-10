/**
 * Model tier pricing mirroring backend/shared/constants.py MODEL_PRICING.
 * Prices are per 1M tokens.
 */
export const MODEL_TIERS = {
  'tier-1': { input: 0.30, output: 0.60, name: 'Llama 3.1 8B' },
  'tier-2': { input: 0.99, output: 0.99, name: 'Llama 3.1 70B' },
  'tier-3': { input: 3.00, output: 15.00, name: 'Claude 3.5 Sonnet' },
} as const

/**
 * Estimate cost range for a given number of records.
 * Assumes ~500 input + 500 output tokens per record.
 * Returns min (tier-1) and max (tier-3) estimates.
 */
export function estimateCostRange(numRecords: number): { min: number; max: number } {
  const tokensPerRecord = 500
  const min = numRecords * (tokensPerRecord / 1e6) * (MODEL_TIERS['tier-1'].input + MODEL_TIERS['tier-1'].output)
  const max = numRecords * (tokensPerRecord / 1e6) * (MODEL_TIERS['tier-3'].input + MODEL_TIERS['tier-3'].output)
  return { min, max }
}
