declare namespace JSX {
  interface IntrinsicElements {
    [elemName: string]: any;
  }
}

declare module "react" {
  export = React;
  export as namespace React;
  namespace React {
    export type ReactNode = any;
    export type ChangeEvent<T = any> = { target: T; [key: string]: any };
    export function useState<T>(initialState: T | (() => T)): [T, (newState: T | ((prev: T) => T)) => void];
    export function useEffect(effect: () => void | (() => void), deps?: any[]): void;
    export function useRef<T>(initialValue: T): { current: T };
    export function createElement(type: any, props?: any, ...children: any[]): any;
  }
}

declare module "react/jsx-runtime" {
  export const jsx: any;
  export const jsxs: any;
  export const Fragment: any;
}

declare module "next" {
  export type Metadata = {
    title?: string;
    description?: string;
    [key: string]: any;
  };
}

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
  export function Modal(props: { isOpen: boolean; onClose: () => void; title: string; children: any; theme?: ThemeTokens; maxWidth?: string }): any;
  export function Switch(props: { checked: boolean; onChange: (checked: boolean) => void; label?: string; theme?: ThemeTokens; disabled?: boolean }): any;
  export function Slider(props: { value: number; min: number; max: number; step?: number; onChange: (value: number) => void; label?: string; unit?: string; theme?: ThemeTokens }): any;
  export function Button(props: any): any;
  export function Badge(props: any): any;
  export function Card(props: any): any;
}
