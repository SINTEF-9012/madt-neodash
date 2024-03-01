import * as React from 'react';
import { useEffect, useState } from 'react';

import {
  Chord,
  useWidth,
} from 'cl-react-graph';

export function ChordChart(props: {rvalue:string}){


  const {rvalue} = props;
  const [ref, width] = useWidth('90%');
  const data = JSON.parse(rvalue)
  return (
        //<SimpleText text={queryResult} />
    <div>
      <Chord
        width={300}
        height={300}
        data={ data } />
    </div> 
  );
}