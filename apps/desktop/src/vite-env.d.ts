declare namespace JSX {
  interface IntrinsicElements {
    [elemName: string]: any;
  }
}

// react and react/jsx-runtime are typed by the real @types/react package
// (a genuine devDependency) -- a hand-written ambient shim used to live here
// with only a handful of exports (no StrictMode, no ReactDOM types, etc.),
// which silently shadowed the real types and made anything it didn't stub
// out look like a type error instead of just working.

declare module "@saleha/ui" {
  export interface ThemeTokens {
    name: string;
    id: string;
    bgBase: string;
    bgSurface: string;
    bgElevated: string;
    bgHover: string;
    borderSubtle: string;
    borderBright: string;
    accent: string;
    accentGlow: string;
    accentPurple: string;
    accentGreen: string;
    accentAmber: string;
    accentRed: string;
    textBright: string;
    textMain: string;
    textDim: string;
    glassBlur: string;
  }
  export const THEME_PRESETS: Record<string, ThemeTokens>;
  export const DEFAULT_THEME: ThemeTokens;
  export function applyThemeToDom(theme: ThemeTokens): void;
  export function Modal(props: { isOpen: boolean; onClose: () => void; title: string; children?: any; theme?: ThemeTokens; maxWidth?: string }): any;
  export function Switch(props: { checked: boolean; onChange: (checked: boolean) => void; label?: string; theme?: ThemeTokens; disabled?: boolean }): any;
  export function Slider(props: { value: number; min: number; max: number; step?: number; onChange: (value: number) => void; label?: string; unit?: string; theme?: ThemeTokens }): any;
  export function Button(props: any): any;
  export function Badge(props: any): any;
  export function Card(props: any): any;
}
