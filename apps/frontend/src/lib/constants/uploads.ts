/**
 * Limits for every resume upload — the bulk upload and the add-lead drafts.
 * Mirror of RESUME_BATCH_MAX_FILES / RESUME_MAX_BYTES in the backend's
 * recruitment/utils/constants.py, which enforces them; these only let the page
 * say no before a file is sent.
 */
export const RESUME_BATCH_MAX_FILES = 20;
export const RESUME_MAX_BYTES = 5 * 1024 * 1024;
export const RESUME_LIMITS_LABEL = `up to ${RESUME_BATCH_MAX_FILES} files, 5 MB each`;
