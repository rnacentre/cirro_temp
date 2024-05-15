/* import {SvgIcon} from '@mui/material';
import React from 'react'; */

/* export default function CirroIcon() {
  return (
    <SvgIcon style={{verticalAlign: 'text-bottom', paddingBottom: 3}}>
      <path
        d="M19.21 12.04l-1.53-.11-.3-1.5C16.88 7.86 14.62 6 12 6 9.94 6 8.08 7.14 7.12 8.96l-.5.95-1.07.11C3.53 10.24 2 11.95 2 14c0 2.21 1.79 4 4 4h13c1.65 0 3-1.35 3-3 0-1.55-1.22-2.86-2.79-2.96z"
        fill="#4285F4"
      ></path>
      <path d="M19.35 10.04C18.67 6.59 15.64 4 12 4 9.11 4 6.6 5.64 5.35 8.04 2.34 8.36 0 10.91 0 14c0 3.31 2.69 6 6 6h13c2.76 0 5-2.24 5-5 0-2.64-2.05-4.78-4.65-4.96zM19 18H6c-2.21 0-4-1.79-4-4 0-2.05 1.53-3.76 3.56-3.97l1.07-.11.5-.95C8.08 7.14 9.94 6 12 6c2.62 0 4.88 1.86 5.39 4.43l.3 1.5 1.53.11c1.56.1 2.78 1.41 2.78 2.96 0 1.65-1.35 3-3 3z"></path>
    </SvgIcon>
  );
} */

/* export default function CirroIcon() {
  return (
    <SvgIcon style={{transform: 'scale(0.5)', width: '30', height: '30', verticalAlign: 'text-bottom', paddingBottom: 3}}>
  <g id="Layer_1" data-name="Layer 1">
    <path class="cls-1" d="M59.04,32.32c0-5.76-4.67-10.43-10.43-10.43h-21.38v27.53c-10.9-.69-19.56-9.77-19.56-20.85S17.05,7.67,28.57,7.67c7.71,0,14.45,4.2,18.07,10.42h2.8c2.24,0,4.35.52,6.24,1.44C51.88,8.2,41.16,0,28.57,0,12.81,0,0,12.82,0,28.57s12.1,27.84,27.23,28.53v.03h10.94v-14.38h10.43c5.76,0,10.43-4.67,10.43-10.43h.01ZM45.39,35.92h-7.22v-7.2h7.22c1.99,0,3.6,1.61,3.6,3.6s-1.61,3.6-3.6,3.6Z"/>
    <polygon class="cls-1" points="41.58 45.48 47.4 57.12 59.71 57.12 53.31 45.66 41.58 45.48"/>
  </g>
</SvgIcon>
  );
} */

import React from "react";
import { ReactComponent as Logo } from "./logo/logo.svg";
import {SvgIcon} from '@mui/material';

/* const App = () => (
  <SvgIcon>
    <Logo />
  </SvgIcon>
);

export default App; */

export default function CirroIcon() {
  return (
    <SvgIcon style={{width: '100', height: '60'}}>
      <Logo /> 
    </SvgIcon>
  );
}