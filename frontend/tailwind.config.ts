import type { Config } from "tailwindcss";

const config: Config = {
	content: [
		"./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
		"./src/components/**/*.{js,ts,jsx,tsx,mdx}",
		"./src/app/**/*.{js,ts,jsx,tsx,mdx}"
	],
	theme: {
		extend: {
			colors: {
				slateBg: "#f4f6fb",
				slateSurface: "#f0f2f8",
				slateBorder: "#e2e5ef",
				slateText: "#0f1629",
				slateMuted: "#7a85a3",
				brandBlue: "#2563eb"
			},
			boxShadow: {
				card: "0 1px 3px rgba(0,0,0,.06),0 4px 16px rgba(0,0,0,.06)",
				cardLg: "0 8px 32px rgba(0,0,0,.12)"
			},
			borderRadius: {
				xl2: "16px"
			}
		}
	},
	plugins: []
};

export default config;
