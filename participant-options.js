export function participantValue(value) {
  if (typeof value !== 'string' || !/^[Pp]?\d{1,3}$/.test(value.trim())) return '';
  const number = Number(value.trim().replace(/^[Pp]/, ''));
  return Number.isInteger(number) && number <= 100 ? String(number) : '';
}

export function participantOptions(select, recorded) {
  const status = recorded === null ? null : recorded || [];
  const signature = JSON.stringify(status);
  if (select.dataset.recordedSignature === signature) return;
  const current = select.value;
  const used = new Set(Array.isArray(status) ? status : []);
  const placeholder = new Option(status === null ? 'History unavailable — choose number' : 'Choose participant number', '');
  const options = [placeholder];
  for (let number = 0; number <= 100; number++) {
    const option = new Option(`${number}${used.has(number) ? ' · recorded' : ''}`, String(number));
    if (used.has(number)) option.dataset.recorded = 'true';
    options.push(option);
  }
  select.replaceChildren(...options);
  select.value = current;
  select.dataset.recordedSignature = signature;
}

export function selectParticipant(select, value) {
  select.value = participantValue(value);
  select.dataset.recorded = select.selectedOptions[0]?.dataset.recorded || 'false';
}
