export interface TimeSortable {
    [key: string]: () => Date;
}

export const sortByTime = (getTimeFnName: string) => {
return (a: TimeSortable, b: TimeSortable): number => {
    const startTimeA = a[getTimeFnName]() || new Date(0); // Use epoch time for empty start times
    const startTimeB = b[getTimeFnName]() || new Date(0); // Use epoch time for empty start times
    if (startTimeA < startTimeB) return -1;
    if (startTimeA > startTimeB) return 1;
    return 0;
};
};

  export const formatDuration = (seconds: number): string => {
    seconds = Math.floor(seconds); // Round down to the nearest integer
    const days = Math.floor(seconds / (24 * 3600));
    seconds %= 24 * 3600;
    const hours = Math.floor(seconds / 3600);
    seconds %= 3600;
    const minutes = Math.floor(seconds / 60);
    seconds %= 60;
  
    const daysStr = days > 0 ? `${days}d ` : '';
    const hoursStr = hours > 0 ? `${hours.toString().padStart(2, '0')}:` : '00:';
    const minutesStr = minutes > 0 ? `${minutes.toString().padStart(2, '0')}:` : '00:';
    const secondsStr = seconds > 0 ? `${seconds.toString().padStart(2, '0')}` : '00';
  
    return `${daysStr}${hoursStr}${minutesStr}${secondsStr}`;
  };