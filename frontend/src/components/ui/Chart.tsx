import * as React from 'react';
import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';
import { cn } from '@/lib/utils';

export interface ChartProps {
  option: EChartsOption;
  height?: number | string;
  className?: string;
  title?: string;
  loading?: boolean;
  notMerge?: boolean;
}

/** Wrapper de ECharts (Apache) con el estilo de la casa. */
export function Chart({ option, height = 300, className, title, loading, notMerge = true }: ChartProps) {
  return (
    <div className={cn('w-full', className)}>
      {title && <h4 className="mb-2 text-sm font-semibold">{title}</h4>}
      <ReactECharts
        option={option}
        style={{ height, width: '100%' }}
        showLoading={loading}
        notMerge={notMerge}
        lazyUpdate
      />
    </div>
  );
}
