import { Eye, EyeOff, Loader2 } from "lucide-react";
import type { InputHTMLAttributes, ReactNode } from "react";

export const authInputClass =
  "auth-input h-11 w-full rounded-lg border border-black/10 bg-mist px-4 font-body text-[17px] text-bark outline-none focus:border-canopy focus:ring-2 focus:ring-leaf";

export const authErrorClass = "mt-2 font-body text-sm leading-[1.5] text-red-700";

export function passwordRules(password: string) {
  return [
    { id: "length", label: "12 to 20 characters", ok: password.length >= 12 && password.length <= 20 },
    { id: "upper", label: "An uppercase letter", ok: /[A-Z]/.test(password) },
    { id: "lower", label: "A lowercase letter", ok: /[a-z]/.test(password) },
    { id: "number", label: "A number", ok: /\d/.test(password) },
    { id: "symbol", label: "A symbol", ok: /[^A-Za-z0-9]/.test(password) },
  ];
}

export function focusField(id: string) {
  document.getElementById(id)?.focus();
}

type FieldProps = {
  id: string;
  label: ReactNode;
  error?: string;
} & InputHTMLAttributes<HTMLInputElement>;

export function AuthField({ id, label, error, className, ...props }: FieldProps) {
  const errorId = `${id}-error`;
  return (
    <div className="mt-4">
      <div className="mb-2 flex items-center justify-between gap-4">
        <label htmlFor={id} className="font-body text-sm font-semibold leading-[1.4] text-bark">
          {label}
        </label>
      </div>
      <input
        id={id}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? errorId : undefined}
        className={`${authInputClass} ${className ?? ""}`}
        {...props}
      />
      {error ? (
        <p id={errorId} className={authErrorClass} role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

type PasswordFieldProps = FieldProps & {
  shown: boolean;
  onToggle: () => void;
  labelExtra?: ReactNode;
};

export function PasswordField({
  id,
  label,
  labelExtra,
  error,
  shown,
  onToggle,
  className,
  "aria-describedby": describedBy,
  ...props
}: PasswordFieldProps) {
  const errorId = `${id}-error`;
  const described = [describedBy, error ? errorId : null].filter(Boolean).join(" ") || undefined;
  return (
    <div className="mt-4">
      <div className="mb-2 flex items-center justify-between gap-4">
        <label htmlFor={id} className="font-body text-sm font-semibold leading-[1.4] text-bark">
          {label}
        </label>
        {labelExtra}
      </div>
      <div className="relative">
        <input
          id={id}
          {...props}
          type={shown ? "text" : "password"}
          aria-invalid={Boolean(error)}
          aria-describedby={described}
          className={`${authInputClass} pr-12 ${className ?? ""}`}
        />
        <button
          type="button"
          className="absolute right-3 top-1/2 -translate-y-1/2 text-stone"
          aria-label={shown ? "Hide password" : "Show password"}
          aria-pressed={shown}
          onClick={onToggle}
        >
          {shown ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
        </button>
      </div>
      {error ? (
        <p id={errorId} className={authErrorClass} role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
}

export function AuthSubmit({
  busy,
  busyLabel,
  children,
  disabled,
}: {
  busy: boolean;
  busyLabel: string;
  children: ReactNode;
  disabled?: boolean;
}) {
  return (
    <button
      className="mt-8 inline-flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-canopy font-body text-[17px] font-semibold text-chalk transition-all duration-200 ease-[ease] hover:-translate-y-0.5 hover:bg-soil disabled:translate-y-0 disabled:cursor-not-allowed disabled:opacity-60"
      type="submit"
      disabled={disabled || busy}
    >
      {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : null}
      {busy ? busyLabel : children}
    </button>
  );
}

export function FormAlert({ children }: { children: ReactNode }) {
  return (
    <p className="mt-4 font-body text-sm leading-[1.5] text-red-700" role="alert">
      {children}
    </p>
  );
}
