// Job lifecycle helpers shared across the grid and detail views.
export const ACTIVE = new Set(['processing', 'searching', 'scraping', 'summarizing']);

export const isActive = (status) => ACTIVE.has(status);

export const STATUS_LABEL = {
  processing: 'Starting…',
  searching: 'Searching…',
  scraping: 'Visiting sites…',
  summarizing: 'Summarizing…',
  done: 'Done',
  error: 'Failed',
};
