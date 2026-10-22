import * as React from 'react';
import { cn } from '@/lib/utils';
import { RadioGroup, RadioGroupItem } from './RadioGroup';
import { Label } from './Label';
import { Checkbox } from './Checkbox';
import { Button } from './Button';

export interface QuestionOption {
  value: string;
  label: string;
}

export interface Question {
  id: string;
  text: string;
  type: 'single' | 'multiple';
  options: QuestionOption[];
}

export interface QuestionnaireProps {
  questions: Question[];
  onSubmit?: (answers: Record<string, string[]>) => void;
  className?: string;
  submitLabel?: string;
}

export function Questionnaire({ questions, onSubmit, className, submitLabel = 'Enviar respuestas' }: QuestionnaireProps) {
  const [answers, setAnswers] = React.useState<Record<string, string[]>>({});

  const setSingle = (qid: string, v: string) => setAnswers((a) => ({ ...a, [qid]: [v] }));
  const toggleMulti = (qid: string, v: string) =>
    setAnswers((a) => {
      const cur = a[qid] ?? [];
      return { ...a, [qid]: cur.includes(v) ? cur.filter((x) => x !== v) : [...cur, v] };
    });

  return (
    <div className={cn('space-y-6', className)}>
      {questions.map((q, i) => (
        <fieldset key={q.id} className="space-y-3 rounded-lg border p-4">
          <legend className="px-1 text-sm font-semibold">
            <span className="mr-2 text-muted-foreground">{i + 1}.</span>{q.text}
          </legend>
          {q.type === 'single' ? (
            <RadioGroup value={answers[q.id]?.[0] ?? ''} onValueChange={(v) => setSingle(q.id, v)}>
              {q.options.map((o) => (
                <div key={o.value} className="flex items-center gap-2">
                  <RadioGroupItem value={o.value} id={`${q.id}-${o.value}`} />
                  <Label htmlFor={`${q.id}-${o.value}`}>{o.label}</Label>
                </div>
              ))}
            </RadioGroup>
          ) : (
            <div className="space-y-2">
              {q.options.map((o) => (
                <div key={o.value} className="flex items-center gap-2">
                  <Checkbox
                    id={`${q.id}-${o.value}`}
                    checked={(answers[q.id] ?? []).includes(o.value)}
                    onCheckedChange={() => toggleMulti(q.id, o.value)}
                  />
                  <Label htmlFor={`${q.id}-${o.value}`}>{o.label}</Label>
                </div>
              ))}
            </div>
          )}
        </fieldset>
      ))}
      {onSubmit && (
        <Button onClick={() => onSubmit(answers)} disabled={Object.keys(answers).length < questions.length}>
          {submitLabel}
        </Button>
      )}
    </div>
  );
}
