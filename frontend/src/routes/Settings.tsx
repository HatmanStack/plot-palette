import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useToast } from '../hooks/useToast'
import {
  fetchNotificationPreferences,
  updateNotificationPreferences,
  type NotificationPreferences,
} from '../services/api'

const defaultPrefs: NotificationPreferences = {
  email_enabled: false,
  email_address: null,
  webhook_enabled: false,
  webhook_url: null,
  notify_on_complete: true,
  notify_on_failure: true,
  notify_on_budget_exceeded: true,
}

function PreferencesForm({ initialPrefs }: { initialPrefs: NotificationPreferences }) {
  const { toast } = useToast()
  const queryClient = useQueryClient()

  const [form, setForm] = useState<NotificationPreferences>(initialPrefs)
  const [isDirty, setIsDirty] = useState(false)
  const [webhookError, setWebhookError] = useState('')

  const mutation = useMutation({
    mutationFn: updateNotificationPreferences,
    onSuccess: (data) => {
      queryClient.setQueryData(['notification-preferences'], data)
      setForm(data)
      setIsDirty(false)
      toast('Preferences saved', 'success')
    },
    onError: (err) => {
      toast(err instanceof Error ? err.message : 'Failed to save preferences', 'error')
    },
  })

  function updateField<K extends keyof NotificationPreferences>(
    key: K,
    value: NotificationPreferences[K],
  ) {
    setForm((prev) => ({ ...prev, [key]: value }))
    setIsDirty(true)
    if (key === 'webhook_url') {
      setWebhookError('')
    }
  }

  function handleSave() {
    if (form.webhook_enabled && !form.webhook_url?.trim()) {
      setWebhookError('Webhook URL is required when webhooks are enabled')
      return
    }
    if (form.webhook_enabled && form.webhook_url && !form.webhook_url.startsWith('https://')) {
      setWebhookError('Webhook URL must start with https://')
      return
    }
    mutation.mutate(form)
  }

  return (
    <div className="space-y-6">
      {/* Email notifications */}
      <div>
        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={form.email_enabled}
            onChange={(e) => updateField('email_enabled', e.target.checked)}
            className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          <span className="font-medium">Email notifications</span>
        </label>

        {form.email_enabled && (
          <div className="mt-3 ml-7">
            <label htmlFor="email_address" className="block text-sm text-gray-600 mb-1">
              Email address
            </label>
            <input
              id="email_address"
              type="email"
              value={form.email_address || ''}
              onChange={(e) => updateField('email_address', e.target.value || null)}
              placeholder="your@email.com"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
        )}
      </div>

      {/* Webhook notifications */}
      <div>
        <label className="flex items-center gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={form.webhook_enabled}
            onChange={(e) => updateField('webhook_enabled', e.target.checked)}
            className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
          />
          <span className="font-medium">Webhook notifications</span>
        </label>

        {form.webhook_enabled && (
          <div className="mt-3 ml-7">
            <label htmlFor="webhook_url" className="block text-sm text-gray-600 mb-1">
              Webhook URL (HTTPS only)
            </label>
            <input
              id="webhook_url"
              type="url"
              value={form.webhook_url || ''}
              onChange={(e) => updateField('webhook_url', e.target.value || null)}
              placeholder="https://example.com/webhook"
              aria-invalid={webhookError ? 'true' : undefined}
              aria-describedby={webhookError ? 'webhook-error' : undefined}
              className={`w-full px-3 py-2 border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                webhookError ? 'border-red-500' : 'border-gray-300'
              }`}
            />
            {webhookError && (
              <p id="webhook-error" role="alert" aria-live="assertive" className="mt-1 text-sm text-red-600">{webhookError}</p>
            )}
          </div>
        )}
      </div>

      {/* Event types */}
      <div>
        <h3 className="font-medium mb-3">Notify on</h3>
        <div className="space-y-2 ml-7">
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={form.notify_on_complete}
              onChange={(e) => updateField('notify_on_complete', e.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span className="text-sm">Job completion</span>
          </label>
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={form.notify_on_failure}
              onChange={(e) => updateField('notify_on_failure', e.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span className="text-sm">Job failure</span>
          </label>
          <label className="flex items-center gap-3 cursor-pointer">
            <input
              type="checkbox"
              checked={form.notify_on_budget_exceeded}
              onChange={(e) => updateField('notify_on_budget_exceeded', e.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
            />
            <span className="text-sm">Budget exceeded</span>
          </label>
        </div>
      </div>

      {/* Save button */}
      <div className="pt-4 border-t">
        <button
          onClick={handleSave}
          disabled={!isDirty || mutation.isPending}
          className="px-6 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {mutation.isPending ? 'Saving...' : 'Save Preferences'}
        </button>
      </div>
    </div>
  )
}

export default function Settings() {
  const { data: prefs, isLoading, error } = useQuery({
    queryKey: ['notification-preferences'],
    queryFn: fetchNotificationPreferences,
  })

  if (isLoading) {
    return (
      <div className="max-w-2xl mx-auto">
        <h1 className="text-2xl font-bold mb-6">Settings</h1>
        <div className="text-gray-600">Loading preferences...</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-2xl mx-auto">
        <h1 className="text-2xl font-bold mb-6">Settings</h1>
        <div className="bg-red-50 border border-red-200 text-red-600 px-4 py-3 rounded">
          Error loading preferences: {error instanceof Error ? error.message : 'Unknown error'}
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Settings</h1>

      <div className="bg-white rounded-lg shadow-md p-6">
        <h2 className="text-xl font-semibold mb-4">Notification Preferences</h2>
        <PreferencesForm
          initialPrefs={prefs ?? defaultPrefs}
        />
      </div>
    </div>
  )
}
