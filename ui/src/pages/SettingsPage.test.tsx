import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { SettingsPage } from './SettingsPage';

const mocks = vi.hoisted(() => ({
  api: {
    config: {
      get: vi.fn(),
      update: vi.fn(),
      clearApiKey: vi.fn(),
      testConnection: vi.fn(),
    },
  },
}));

vi.mock('../api/client', () => ({ api: mocks.api }));

const api = mocks.api;

const status = {
  llm_provider: 'openrouter',
  model_name: 'test/model',
  base_url: '',
  temperature: 0.7,
  api_key_masked: 'sk-o\u20269999',
  api_key_source: 'ui',
  has_api_key: true,
  model: 'test/model',
};

beforeEach(() => {
  api.config.get.mockResolvedValue(status);
  api.config.update.mockResolvedValue(status);
  api.config.clearApiKey.mockResolvedValue({ ...status, has_api_key: false, api_key_masked: null });
});

function renderPage() {
  return render(
    <MemoryRouter>
      <SettingsPage />
    </MemoryRouter>
  );
}

async function openModules() {
  renderPage();
  await waitFor(() => expect(api.config.get).toHaveBeenCalled());
  fireEvent.click(screen.getByText('Modules'));
  return document.querySelector('input[type="password"]') as HTMLInputElement;
}

describe('SettingsPage secret handling', () => {
  it('never loads the raw key into the form and shows the masked hint', async () => {
    const keyInput = await openModules();
    expect(keyInput).toBeTruthy();
    expect(keyInput.value).toBe('');
    expect(keyInput.placeholder).toContain('sk-o\u20269999');
  });

  it('saving with a blank key asks the backend to keep the stored key', async () => {
    await openModules();
    fireEvent.click(screen.getByText('Save Configuration'));
    await waitFor(() => expect(api.config.update).toHaveBeenCalled());
    const payload = api.config.update.mock.calls[0][0];
    expect(payload.api_key_action).toBe('keep');
    expect(payload.api_key).toBeUndefined();
  });

  it('typing a new key sends an explicit replace action', async () => {
    const keyInput = await openModules();
    fireEvent.change(keyInput, { target: { value: 'sk-new-secret' } });
    fireEvent.click(screen.getByText('Save Configuration'));
    await waitFor(() => expect(api.config.update).toHaveBeenCalled());
    const payload = api.config.update.mock.calls[0][0];
    expect(payload.api_key_action).toBe('replace');
    expect(payload.api_key).toBe('sk-new-secret');
  });

  it('the clear button sends an explicit delete action', async () => {
    await openModules();
    fireEvent.click(screen.getByText('Clear Stored Key'));
    await waitFor(() => expect(api.config.update).toHaveBeenCalled());
    const payload = api.config.update.mock.calls[0][0];
    expect(payload.api_key_action).toBe('delete');
  });
});
