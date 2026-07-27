import { Table } from "antd";
import type { TableProps } from "antd";
import type { ColumnsType, ColumnType } from "antd/es/table";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { CSSProperties, PointerEvent, ReactNode, ThHTMLAttributes } from "react";

const STORAGE_PREFIX = "vulnflanker:table-widths:";
const DEFAULT_COLUMN_WIDTH = 180;
const DEFAULT_MIN_COLUMN_WIDTH = 80;

type ColumnWidthMap = Record<string, number>;

interface ResizableHeaderCellProps
  extends ThHTMLAttributes<HTMLTableCellElement> {
  columnKey?: string;
  minColumnWidth?: number;
  onResizeColumn?: (columnKey: string, width: number) => void;
  resizable?: boolean;
  width?: number;
}

export interface ResizableTableProps<RecordType extends object>
  extends TableProps<RecordType> {
  minColumnWidth?: number;
  storageKey: string;
}

function normalizeWidth(value: unknown): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }

  return undefined;
}

function getColumnKey<RecordType extends object>(
  column: ColumnType<RecordType>,
  fallbackKey: string
) {
  if (column.key !== undefined && column.key !== null) {
    return String(column.key);
  }

  const dataIndex = column.dataIndex;
  if (Array.isArray(dataIndex)) {
    return dataIndex.map(String).join(".");
  }

  if (dataIndex !== undefined && dataIndex !== null) {
    return String(dataIndex);
  }

  return fallbackKey;
}

function readStoredWidths(storageKey: string): ColumnWidthMap {
  if (typeof window === "undefined") {
    return {};
  }

  try {
    const stored = window.localStorage.getItem(`${STORAGE_PREFIX}${storageKey}`);
    if (!stored) {
      return {};
    }

    const parsed = JSON.parse(stored) as unknown;
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
      return {};
    }

    return Object.entries(parsed).reduce<ColumnWidthMap>((widths, [key, value]) => {
      const width = normalizeWidth(value);
      if (width) {
        widths[key] = width;
      }
      return widths;
    }, {});
  } catch {
    return {};
  }
}

function storeWidths(storageKey: string, widths: ColumnWidthMap) {
  if (typeof window === "undefined") {
    return;
  }

  window.localStorage.setItem(`${STORAGE_PREFIX}${storageKey}`, JSON.stringify(widths));
}

function HeaderCell({
  children,
  className,
  columnKey,
  minColumnWidth = DEFAULT_MIN_COLUMN_WIDTH,
  onResizeColumn,
  resizable,
  style,
  width,
  ...rest
}: ResizableHeaderCellProps) {
  function handlePointerDown(event: PointerEvent<HTMLSpanElement>) {
    if (!resizable || !columnKey || !onResizeColumn || !width || event.button !== 0) {
      return;
    }

    event.preventDefault();
    event.stopPropagation();

    const startX = event.clientX;
    const startWidth = width;
    const previousCursor = document.body.style.cursor;
    const previousUserSelect = document.body.style.userSelect;

    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    const handlePointerMove = (moveEvent: globalThis.PointerEvent) => {
      const nextWidth = Math.max(
        minColumnWidth,
        Math.round(startWidth + moveEvent.clientX - startX)
      );
      onResizeColumn(columnKey, nextWidth);
    };

    const handlePointerUp = () => {
      window.removeEventListener("pointermove", handlePointerMove);
      window.removeEventListener("pointerup", handlePointerUp);
      document.body.style.cursor = previousCursor;
      document.body.style.userSelect = previousUserSelect;
    };

    window.addEventListener("pointermove", handlePointerMove);
    window.addEventListener("pointerup", handlePointerUp);
  }

  const headerStyle: CSSProperties = {
    ...style,
    minWidth: width,
    width
  };

  return (
    <th
      {...rest}
      className={[className, "resizable-table-header-cell"].filter(Boolean).join(" ")}
      style={headerStyle}
    >
      {children as ReactNode}
      {resizable ? (
        <span
          aria-hidden="true"
          className="resizable-table-handle"
          onClick={(event) => event.stopPropagation()}
          onPointerDown={handlePointerDown}
        />
      ) : null}
    </th>
  );
}

function getColumnBaseWidth<RecordType extends object>(column: ColumnType<RecordType>) {
  return (
    normalizeWidth(column.width) ??
    normalizeWidth(column.minWidth) ??
    DEFAULT_COLUMN_WIDTH
  );
}

function buildResizableColumns<RecordType extends object>(
  columns: ColumnsType<RecordType>,
  widths: ColumnWidthMap,
  minColumnWidth: number,
  onResizeColumn: (columnKey: string, width: number) => void,
  path: number[] = []
): ColumnsType<RecordType> {
  return columns.map((column, index) => {
    const fallbackKey = `column-${[...path, index].join("-")}`;
    const key = getColumnKey(column as ColumnType<RecordType>, fallbackKey);
    const baseWidth = getColumnBaseWidth(column as ColumnType<RecordType>);
    const width = Math.max(minColumnWidth, widths[key] ?? baseWidth);

    if ("children" in column && column.children?.length) {
      return {
        ...column,
        children: buildResizableColumns(
          column.children,
          widths,
          minColumnWidth,
          onResizeColumn,
          [...path, index]
        )
      };
    }

    const currentColumn = column as ColumnType<RecordType>;
    const existingHeaderCell = currentColumn.onHeaderCell;

    return {
      ...currentColumn,
      width,
      onHeaderCell: (renderColumn) => {
        const headerCellProps = existingHeaderCell?.(renderColumn) ?? {};
        return {
          ...headerCellProps,
          columnKey: key,
          minColumnWidth,
          onResizeColumn,
          resizable: true,
          width
        } as ThHTMLAttributes<HTMLTableCellElement>;
      }
    };
  });
}

function sumColumnWidths<RecordType extends object>(
  columns: ColumnsType<RecordType>
): number {
  return columns.reduce((total, column) => {
    if ("children" in column && column.children?.length) {
      return total + sumColumnWidths(column.children);
    }
    return total + getColumnBaseWidth(column as ColumnType<RecordType>);
  }, 0);
}

export default function ResizableTable<RecordType extends object>({
  className,
  columns,
  minColumnWidth = DEFAULT_MIN_COLUMN_WIDTH,
  scroll,
  storageKey,
  tableLayout,
  ...tableProps
}: ResizableTableProps<RecordType>) {
  const [widths, setWidths] = useState<ColumnWidthMap>(() => readStoredWidths(storageKey));

  useEffect(() => {
    setWidths(readStoredWidths(storageKey));
  }, [storageKey]);

  const handleResizeColumn = useCallback(
    (columnKey: string, width: number) => {
      setWidths((currentWidths) => {
        const nextWidths = {
          ...currentWidths,
          [columnKey]: width
        };
        storeWidths(storageKey, nextWidths);
        return nextWidths;
      });
    },
    [storageKey]
  );

  const resizableColumns = useMemo(
    () =>
      columns
        ? buildResizableColumns(columns, widths, minColumnWidth, handleResizeColumn)
        : columns,
    [columns, handleResizeColumn, minColumnWidth, widths]
  );

  const scrollX = useMemo(() => {
    if (!resizableColumns) {
      return scroll?.x;
    }

    return Math.max(sumColumnWidths(resizableColumns), normalizeWidth(scroll?.x) ?? 0);
  }, [resizableColumns, scroll?.x]);

  return (
    <Table<RecordType>
      {...tableProps}
      className={["resizable-table", className].filter(Boolean).join(" ")}
      columns={resizableColumns}
      components={{
        ...(tableProps.components ?? {}),
        header: {
          ...(tableProps.components?.header ?? {}),
          cell: HeaderCell
        }
      }}
      scroll={{
        ...scroll,
        x: scrollX
      }}
      tableLayout={tableLayout ?? "fixed"}
    />
  );
}
