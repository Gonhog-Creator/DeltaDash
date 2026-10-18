import { useEffect, useRef, useState } from 'react';
import { X } from 'lucide-react';

type Operator = '+' | '-' | '*' | '/';

const OP_SYMBOL: Record<Operator, string> = { '+': '+', '-': '−', '*': '×', '/': '÷' };

interface CalculatorModalProps {
  onClose: () => void;
}

function compute(a: number, b: number, op: Operator): number {
  const r = op === '+' ? a + b : op === '-' ? a - b : op === '*' ? a * b : a / b;
  // Trim float noise (0.1 + 0.2 = 0.3, not 0.30000000000000004)
  return parseFloat(r.toPrecision(12));
}

function format(value: number): string {
  if (!Number.isFinite(value)) return 'Error';
  return String(parseFloat(value.toPrecision(12)));
}

export function CalculatorModal({ onClose }: CalculatorModalProps) {
  const [display, setDisplay] = useState('0');
  const [accumulator, setAccumulator] = useState<number | null>(null);
  const [pendingOp, setPendingOp] = useState<Operator | null>(null);
  const [waitingForOperand, setWaitingForOperand] = useState(false);
  const [copied, setCopied] = useState(false);
  const modalRef = useRef<HTMLDivElement>(null);

  const clearAll = () => {
    setDisplay('0');
    setAccumulator(null);
    setPendingOp(null);
    setWaitingForOperand(false);
  };

  const inputDigit = (d: string) => {
    if (display === 'Error') clearAll();
    if (waitingForOperand) {
      setDisplay(d);
      setWaitingForOperand(false);
    } else {
      setDisplay((prev) => (prev === '0' ? d : prev.length < 15 ? prev + d : prev));
    }
  };

  const inputDot = () => {
    if (waitingForOperand) {
      setDisplay('0.');
      setWaitingForOperand(false);
    } else if (!display.includes('.')) {
      setDisplay((prev) => prev + '.');
    }
  };

  const backspace = () => {
    if (waitingForOperand) return;
    setDisplay((prev) => (prev.length <= 1 || prev === 'Error' ? '0' : prev.slice(0, -1)));
  };

  const negate = () => {
    if (display !== '0' && display !== 'Error') {
      setDisplay((prev) => (prev.startsWith('-') ? prev.slice(1) : '-' + prev));
    }
  };

  const percent = () => {
    const v = parseFloat(display);
    if (!Number.isNaN(v)) setDisplay(format(v / 100));
  };

  const applyOperator = (op: Operator) => {
    const current = parseFloat(display);
    if (Number.isNaN(current)) return;
    if (accumulator !== null && pendingOp && !waitingForOperand) {
      const result = compute(accumulator, current, pendingOp);
      setAccumulator(result);
      setDisplay(format(result));
    } else {
      setAccumulator(current);
    }
    setPendingOp(op);
    setWaitingForOperand(true);
  };

  const equals = async () => {
    if (accumulator === null || pendingOp === null) return;
    const current = parseFloat(display);
    if (Number.isNaN(current)) return;
    const result = compute(accumulator, current, pendingOp);
    const text = format(result);
    setDisplay(text);
    setAccumulator(null);
    setPendingOp(null);
    setWaitingForOperand(true);
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  const handleKey = (key: string) => {
    if (key >= '0' && key <= '9') inputDigit(key);
    else if (key === '.' || key === ',') inputDot();
    else if (key === '+') applyOperator('+');
    else if (key === '-') applyOperator('-');
    else if (key === '*' || key === 'x' || key === 'X') applyOperator('*');
    else if (key === '/') applyOperator('/');
    else if (key === 'Enter' || key === '=') equals();
    else if (key === 'Backspace') backspace();
    else if (key === 'c' || key === 'C') clearAll();
    else if (key === '%') percent();
  };

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.stopImmediatePropagation();
        onClose();
        return;
      }
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const handled = /^[0-9]$/.test(e.key) ||
        ['.', ',', '+', '-', '*', 'x', 'X', '/', 'Enter', '=', 'Backspace', 'c', 'C', '%'].includes(e.key);
      if (handled) {
        e.preventDefault();
        handleKey(e.key);
      }
    };
    // Capture phase so Escape doesn't also close a modal underneath.
    window.addEventListener('keydown', onKeyDown, true);
    modalRef.current?.focus();
    return () => window.removeEventListener('keydown', onKeyDown, true);
  });

  const trail =
    accumulator !== null && pendingOp ? `${format(accumulator)} ${OP_SYMBOL[pendingOp]}` : '';

  const btnBase =
    'h-12 rounded-lg text-lg font-medium transition-colors focus:outline-none select-none';
  const btnNum = `${btnBase} bg-gray-100 hover:bg-gray-200 text-gray-900`;
  const btnOp = `${btnBase} bg-orange-500 hover:bg-orange-600 text-white`;
  const btnFn = `${btnBase} bg-gray-200 hover:bg-gray-300 text-gray-800`;

  const keys: { label: string; onClick: () => void; cls: string; span?: number }[] = [
    { label: 'C', onClick: clearAll, cls: btnFn },
    { label: '±', onClick: negate, cls: btnFn },
    { label: '%', onClick: percent, cls: btnFn },
    { label: '÷', onClick: () => applyOperator('/'), cls: btnOp },
    { label: '7', onClick: () => inputDigit('7'), cls: btnNum },
    { label: '8', onClick: () => inputDigit('8'), cls: btnNum },
    { label: '9', onClick: () => inputDigit('9'), cls: btnNum },
    { label: '×', onClick: () => applyOperator('*'), cls: btnOp },
    { label: '4', onClick: () => inputDigit('4'), cls: btnNum },
    { label: '5', onClick: () => inputDigit('5'), cls: btnNum },
    { label: '6', onClick: () => inputDigit('6'), cls: btnNum },
    { label: '−', onClick: () => applyOperator('-'), cls: btnOp },
    { label: '1', onClick: () => inputDigit('1'), cls: btnNum },
    { label: '2', onClick: () => inputDigit('2'), cls: btnNum },
    { label: '3', onClick: () => inputDigit('3'), cls: btnNum },
    { label: '+', onClick: () => applyOperator('+'), cls: btnOp },
    { label: '0', onClick: () => inputDigit('0'), cls: btnNum, span: 2 },
    { label: '.', onClick: inputDot, cls: btnNum },
    { label: '=', onClick: equals, cls: `${btnBase} bg-blue-600 hover:bg-blue-700 text-white` },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div
        ref={modalRef}
        tabIndex={-1}
        className="relative bg-white rounded-lg shadow-xl w-72 mx-4 p-4 outline-none"
      >
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-gray-500">Calculator</span>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600" aria-label="Close">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="mb-3 px-2 text-right">
          <div className="h-5 text-xs text-gray-400 font-mono truncate">
            {copied ? 'Copied to clipboard' : trail || '\u00A0'}
          </div>
          <div className="text-4xl font-mono text-gray-900 truncate">{display}</div>
        </div>

        <div className="grid grid-cols-4 gap-1.5">
          {keys.map((k) => (
            <button
              key={k.label}
              onClick={k.onClick}
              className={`${k.cls} ${k.span === 2 ? 'col-span-2' : ''}`}
            >
              {k.label}
            </button>
          ))}
        </div>

        <p className="mt-3 text-center text-xs text-gray-400">
          Esc = close · Ctrl+Alt+C = open · = copies result
        </p>
      </div>
    </div>
  );
}
