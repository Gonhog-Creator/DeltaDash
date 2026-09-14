import { useState, useRef, useEffect, useCallback } from 'react';
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  ColumnDef,
} from '@tanstack/react-table';
import { Trash2, Plus } from 'lucide-react';

export interface ShotRowData {
  id: string;
  shot_number: string;
  side: string | null;
  angle_degrees: number | null;
  velocity_m_s: number | null;
  trauma_mm: number | null;
  trauma_qualitative: string | null;
}

const SIDE_OPTIONS = ['Front', 'Back'];
const TRAUMA_OPTIONS = ['OK', 'Punctured', 'PERFORO', 'Partial', 'None'];

interface EditableCellProps {
  value: string | number | null;
  onChange: (value: string) => void;
  onEnter: () => void;
  onTab: (shiftKey: boolean) => void;
  type?: 'text' | 'number' | 'select';
  options?: string[];
  align?: 'left' | 'center' | 'right';
}

function EditableCell({ value, onChange, onEnter, onTab, type = 'text', options, align = 'left' }: EditableCellProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [localValue, setLocalValue] = useState(value?.toString() ?? '');
  const inputRef = useRef<HTMLInputElement | HTMLSelectElement>(null);

  useEffect(() => {
    setLocalValue(value?.toString() ?? '');
  }, [value]);

  useEffect(() => {
    if (isEditing && inputRef.current) {
      inputRef.current.focus();
      if (inputRef.current instanceof HTMLInputElement) {
        inputRef.current.select();
      }
    }
  }, [isEditing]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      setIsEditing(false);
      onChange(localValue);
      onEnter();
    } else if (e.key === 'Tab') {
      e.preventDefault();
      setIsEditing(false);
      onChange(localValue);
      onTab(e.shiftKey);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      setIsEditing(false);
      setLocalValue(value?.toString() ?? '');
    }
  };

  const handleBlur = () => {
    setIsEditing(false);
    onChange(localValue);
  };

  const alignClass = align === 'right' ? 'text-right' : align === 'center' ? 'text-center' : 'text-left';

  if (isEditing) {
    if (type === 'select' && options) {
      return (
        <select
          ref={inputRef as React.RefObject<HTMLSelectElement>}
          value={localValue}
          onChange={(e) => setLocalValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={handleBlur}
          className={`w-full px-1 py-0.5 text-sm border border-blue-400 rounded bg-white outline-none ${alignClass}`}
        >
          <option value="">—</option>
          {options.map((opt) => (
            <option key={opt} value={opt}>{opt}</option>
          ))}
        </select>
      );
    }
    return (
      <input
        ref={inputRef as React.RefObject<HTMLInputElement>}
        type={type === 'number' ? 'number' : 'text'}
        value={localValue}
        onChange={(e) => setLocalValue(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={handleBlur}
        className={`w-full px-1 py-0.5 text-sm border border-blue-400 rounded bg-white outline-none ${alignClass}`}
      />
    );
  }

  return (
    <div
      onClick={() => setIsEditing(true)}
      className={`w-full px-1 py-0.5 text-sm cursor-cell hover:bg-blue-50 rounded min-h-[24px] ${alignClass} ${
        value === null || value === '' ? 'text-gray-300' : 'text-gray-800'
      }`}
    >
      {value ?? '—'}
    </div>
  );
}

interface ShotGridProps {
  data: ShotRowData[];
  onChange: (data: ShotRowData[]) => void;
  ballisticLimit: boolean;
}

export function ShotGrid({ data, onChange, ballisticLimit }: ShotGridProps) {
  const [focusedRow, setFocusedRow] = useState<number>(0);
  const [focusedCol, setFocusedCol] = useState<number>(0);

  const updateCell = useCallback((rowIndex: number, columnId: string, value: string) => {
    const newData = [...data];
    if (!newData[rowIndex]) return;
    let parsedValue: string | number | null = value;
    const numColumns = ['angle_degrees', 'velocity_m_s', 'trauma_mm'];
    if (numColumns.includes(columnId)) {
      parsedValue = value === '' ? null : parseFloat(value);
      if (parsedValue !== null && isNaN(parsedValue as number)) parsedValue = null;
    }
    newData[rowIndex] = { ...newData[rowIndex], [columnId]: parsedValue };
    onChange(newData);
  }, [data, onChange]);

  const addRow = useCallback(() => {
    const nextShotNum = String(data.length + 1);
    const newRow: ShotRowData = {
      id: crypto.randomUUID(),
      shot_number: nextShotNum,
      side: null,
      angle_degrees: 0,
      velocity_m_s: null,
      trauma_mm: null,
      trauma_qualitative: null,
    };
    onChange([...data, newRow]);
    setFocusedRow(data.length);
    setFocusedCol(0);
  }, [data, onChange]);

  const deleteRow = useCallback((rowIndex: number) => {
    const newData = data.filter((_, i) => i !== rowIndex);
    // Renumber shots
    newData.forEach((row, i) => {
      row.shot_number = String(i + 1);
    });
    onChange(newData);
  }, [data, onChange]);

  const navigateDown = useCallback(() => {
    if (focusedRow < data.length - 1) {
      setFocusedRow(focusedRow + 1);
    } else {
      addRow();
    }
  }, [focusedRow, data.length, addRow]);

  const columns: ColumnDef<ShotRowData>[] = [
    {
      id: 'shot_number',
      header: '#',
      cell: ({ row }) => (
        <div className="text-center text-sm font-medium text-gray-500 px-1 py-0.5">
          {row.original.shot_number}
        </div>
      ),
      size: 40,
    },
    {
      id: 'side',
      header: 'Side',
      cell: ({ row }) => (
        <EditableCell
          value={row.original.side}
          type="select"
          options={SIDE_OPTIONS}
          onChange={(v) => updateCell(row.index, 'side', v)}
          onEnter={navigateDown}
          onTab={navigateCell}
        />
      ),
      size: 90,
    },
    {
      id: 'angle_degrees',
      header: 'Angle (°)',
      cell: ({ row }) => (
        <EditableCell
          value={row.original.angle_degrees}
          type="number"
          align="right"
          onChange={(v) => updateCell(row.index, 'angle_degrees', v)}
          onEnter={navigateDown}
          onTab={navigateCell}
        />
      ),
      size: 80,
    },
    {
      id: 'velocity_m_s',
      header: 'Vel (m/s)',
      cell: ({ row }) => (
        <EditableCell
          value={row.original.velocity_m_s}
          type="number"
          align="right"
          onChange={(v) => updateCell(row.index, 'velocity_m_s', v)}
          onEnter={navigateDown}
          onTab={navigateCell}
        />
      ),
      size: 90,
    },
    {
      id: 'trauma_mm',
      header: 'Trauma (mm)',
      cell: ({ row }) => (
        <EditableCell
          value={row.original.trauma_mm}
          type="number"
          align="right"
          onChange={(v) => updateCell(row.index, 'trauma_mm', v)}
          onEnter={navigateDown}
          onTab={navigateCell}
        />
      ),
      size: 90,
    },
    ...(ballisticLimit ? [{
      id: 'trauma_qualitative' as const,
      header: 'Result',
      cell: ({ row }: { row: any }) => (
        <EditableCell
          value={row.original.trauma_qualitative}
          type="select"
          options={TRAUMA_OPTIONS}
          onChange={(v) => updateCell(row.index, 'trauma_qualitative', v)}
          onEnter={navigateDown}
          onTab={navigateCell}
        />
      ),
      size: 90,
    }] : []),
    {
      id: 'actions',
      header: '',
      cell: ({ row }) => (
        <button
          onClick={() => deleteRow(row.index)}
          className="p-1 text-gray-400 hover:text-red-500 transition-colors"
          title="Delete row"
        >
          <Trash2 size={14} />
        </button>
      ),
      size: 32,
    },
  ];

  const navigateCell = useCallback((shiftKey: boolean) => {
    const totalCols = columns.length;
    if (shiftKey) {
      if (focusedCol > 0) {
        setFocusedCol(focusedCol - 1);
      } else if (focusedRow > 0) {
        setFocusedRow(focusedRow - 1);
        setFocusedCol(totalCols - 1);
      }
    } else {
      if (focusedCol < totalCols - 1) {
        setFocusedCol(focusedCol + 1);
      } else if (focusedRow < data.length - 1) {
        setFocusedRow(focusedRow + 1);
        setFocusedCol(0);
      }
    }
  }, [focusedCol, focusedRow, data.length, columns.length]);

  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-auto border border-gray-200 rounded-lg">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 sticky top-0 z-10">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    style={{ width: header.getSize() }}
                    className="px-2 py-1.5 text-xs font-semibold text-gray-600 text-left border-b border-gray-200"
                  >
                    {flexRender(header.column.columnDef.header, header.getContext())}
                  </th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row, rowIndex) => (
              <tr
                key={row.id}
                className={`border-b border-gray-100 hover:bg-gray-50 ${
                  rowIndex === focusedRow ? 'bg-blue-50' : ''
                }`}
              >
                {row.getVisibleCells().map((cell, colIndex) => (
                  <td
                    key={cell.id}
                    style={{ width: cell.column.getSize() }}
                    className="border-r border-gray-100"
                    onClick={() => {
                      setFocusedRow(rowIndex);
                      setFocusedCol(colIndex);
                    }}
                  >
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
            ))}
            {data.length === 0 && (
              <tr>
                <td colSpan={columns.length} className="text-center text-gray-400 py-8">
                  No shots yet. Click "Add Shot" to start.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="flex items-center gap-2 mt-2">
        <button
          onClick={addRow}
          className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-blue-600 bg-blue-50 hover:bg-blue-100 rounded-lg transition-colors"
        >
          <Plus size={16} />
          Add Shot
        </button>
        <span className="text-xs text-gray-400">
          {data.length} shot{data.length !== 1 ? 's' : ''}
        </span>
      </div>
    </div>
  );
}
